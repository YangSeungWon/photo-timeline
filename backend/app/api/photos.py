from uuid import UUID
from typing import List, Optional
import logging
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..core.database import get_db
from ..core.deps import get_current_active_user
from ..core.storage import save_upload_file
from ..core.queues import default_queue
from ..models.user import User
from ..models.group import Group
from ..models.membership import Membership, MembershipStatus
from ..models.photo import Photo
from ..models.meeting import Meeting
from ..schemas.photo import PhotoResponse, PhotoUploadResponse
from ..worker_tasks import process_photo

# Add this import for EXIF processing
from PIL import Image
from PIL.ExifTags import TAGS

def extract_photo_datetime(file_path: Path) -> Optional[datetime]:
    """Extract datetime from photo EXIF data."""
    try:
        with Image.open(file_path) as image:
            exif_data = image._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    tag_name = TAGS.get(tag, tag)
                    if tag_name == "DateTimeOriginal" or tag_name == "DateTime":
                        try:
                            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            continue
    except Exception as e:
        logger.warning(f"Failed to extract EXIF datetime from {file_path}: {e}")
    return None

logger = logging.getLogger(__name__)

router = APIRouter()


def find_closest_meeting(
    db: Session, group_id: UUID, shot_at: Optional[datetime]
) -> Optional[Meeting]:
    """Find the closest existing meeting based on the photo's shot date."""
    if not shot_at:
        return None
    
    # Get all meetings for the group, excluding "Default Meeting"
    meetings = db.exec(
        select(Meeting).where(
            Meeting.group_id == group_id,
            Meeting.title != "Default Meeting"
        )
    ).all()
    
    if not meetings:
        return None
    
    # First, try to find a meeting where the photo was taken during the meeting
    for meeting in meetings:
        if meeting.start_time <= shot_at <= meeting.end_time:
            logger.info(f"Photo taken during meeting period: {meeting.title}")
            return meeting
    
    # If no exact match, find the meeting with the closest start time
    closest_meeting = None
    min_time_diff = None
    
    for meeting in meetings:
        # Calculate time difference between shot date and meeting start time
        time_diff = abs((shot_at - meeting.start_time).total_seconds())
        
        if min_time_diff is None or time_diff < min_time_diff:
            min_time_diff = time_diff
            closest_meeting = meeting
    
    # Only assign to meeting if the photo was taken within 48 hours of the meeting
    # This prevents very old photos from being assigned to unrelated meetings
    if min_time_diff and min_time_diff <= 48 * 3600:  # 48 hours in seconds
        logger.info(f"Photo assigned to closest meeting within 48h: {closest_meeting.title} (diff: {min_time_diff/3600:.1f}h)")
        return closest_meeting
    
    logger.info(f"No suitable meeting found (closest diff: {min_time_diff/3600 if min_time_diff else 'N/A'}h)")
    return None


@router.post("/upload", response_model=PhotoUploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    group_id: UUID = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a photo to a group."""
    # Verify group exists and user is a member
    group = db.exec(select(Group).where(Group.id == group_id)).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Check membership
    membership = db.exec(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.group_id == group_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )

    # Save file
    filename, file_path = await save_upload_file(file, str(group_id))
    file_abs_path = Path(file_path).resolve()

    # Extract EXIF data to get shot date
    shot_at = extract_photo_datetime(file_abs_path)
    if shot_at:
        logger.info(f"Extracted shot date from EXIF: {shot_at}")
    else:
        logger.info(f"No shot date found in EXIF for {filename}")

    # Find the closest meeting based on shot date
    target_meeting = None
    if shot_at:
        target_meeting = find_closest_meeting(db, group_id, shot_at)
        if target_meeting:
            logger.info(f"Assigned photo to existing meeting: {target_meeting.title}")

    # If no suitable meeting found, create or get default meeting
    if not target_meeting:
        target_meeting = db.exec(
            select(Meeting).where(
                Meeting.group_id == group_id, Meeting.title == "Default Meeting"
            )
        ).first()

        if not target_meeting:
            now = datetime.utcnow()
            target_meeting = Meeting(
                group_id=group_id,
                title="Default Meeting",
                description="Auto-created meeting for uploaded photos",
                start_time=now,
                end_time=now,
                meeting_date=now.date(),
                photo_count=0,
                participant_count=0,
            )
            db.add(target_meeting)
            db.commit()
            db.refresh(target_meeting)
        
        logger.info("Assigned photo to default meeting")

    # Create photo record
    photo = Photo(
        group_id=group_id,
        uploader_id=current_user.id,
        meeting_id=target_meeting.id,
        filename_orig=filename,
        file_size=file.size or 0,
        file_hash="",  # Will be calculated by worker
        mime_type=file.content_type or "application/octet-stream",
        is_processed=False,
        shot_at=shot_at,  # Store the extracted shot date
    )

    db.add(photo)
    
    # Update meeting photo count
    target_meeting.photo_count += 1
    target_meeting.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(photo)

    # Enqueue background task for processing
    try:
        job = default_queue.enqueue(
            process_photo,
            photo_id=str(photo.id),
            file_path=str(file_abs_path),
            job_timeout=300,  # 5 minutes
        )
        logger.info(f"Enqueued photo processing job {job.id} for photo {photo.id}")

        return PhotoUploadResponse(
            id=photo.id,
            filename=filename,
            status="uploaded",
            message="Photo uploaded successfully. Processing in background.",
        )
    except Exception as e:
        logger.error(f"Failed to enqueue photo processing: {e}")
        # Clean up the photo record if we can't process it
        db.delete(photo)
        db.commit()

        # Try to remove the file
        try:
            file_abs_path.unlink(missing_ok=True)
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue photo for processing",
        )


@router.get("", response_model=List[PhotoResponse])
async def list_photos(
    group_id: Optional[UUID] = Query(None, description="Filter by group ID"),
    meeting_id: Optional[UUID] = Query(None, description="Filter by meeting ID"),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List photos in a group or meeting."""
    query = select(Photo)
    
    if group_id:
        # Verify group access
        group = db.exec(select(Group).where(Group.id == group_id)).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )

        # Check membership
        membership = db.exec(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.group_id == group_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        ).first()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this group",
            )

        query = query.where(Photo.group_id == group_id)
    
    if meeting_id:
        # Verify meeting access through group membership
        meeting = db.exec(select(Meeting).where(Meeting.id == meeting_id)).first()
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
            )
        
        # Check group membership for the meeting's group
        membership = db.exec(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.group_id == meeting.group_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        ).first()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this group",
            )
        
        query = query.where(Photo.meeting_id == meeting_id)

    photos = db.exec(query.offset(offset).limit(limit)).all()
    return [PhotoResponse.from_photo_model(photo) for photo in photos]


@router.get("/{photo_id}", response_model=PhotoResponse)
async def get_photo(
    photo_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific photo."""
    photo = db.exec(select(Photo).where(Photo.id == photo_id)).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
        )

    # Check group membership
    membership = db.exec(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.group_id == photo.group_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )

    return PhotoResponse.from_photo_model(photo)


@router.get("/{photo_id}/full")
async def get_photo_full(
    photo_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the full-size original photo."""
    photo = db.exec(select(Photo).where(Photo.id == photo_id)).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
        )

    # Check group membership
    membership = db.exec(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.group_id == photo.group_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )
    
    # Construct original file path
    orig_path = Path("/srv/photo-timeline/storage") / str(photo.group_id) / photo.filename_orig
    
    if not orig_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Original photo file not found"
        )

    return FileResponse(
        path=str(orig_path),
        media_type=photo.mime_type or "image/jpeg",
        filename=photo.filename_orig
    )


@router.get("/{photo_id}/thumb")
async def get_photo_thumbnail(
    photo_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a photo thumbnail."""
    photo = db.exec(select(Photo).where(Photo.id == photo_id)).first()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
        )

    # Check if thumbnail exists
    if not photo.filename_thumb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Thumbnail not available. Photo may still be processing."
        )

    # Check group membership
    membership = db.exec(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.group_id == photo.group_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )
    
    # Construct thumbnail file path
    # Assuming thumbnails are stored in the same directory structure as originals
    # but with a different filename
    thumb_path = Path("/srv/photo-timeline/storage") / str(photo.group_id) / photo.filename_thumb
    
    if not thumb_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail file not found"
        )

    return FileResponse(
        path=str(thumb_path),
        media_type=photo.mime_type or "image/jpeg",
        filename=photo.filename_thumb
    )
