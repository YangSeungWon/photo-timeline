from uuid import UUID
from typing import List, Optional
import logging
from pathlib import Path
from datetime import datetime
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

logger = logging.getLogger(__name__)

router = APIRouter()


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

    # Create or get default meeting for the group
    default_meeting = db.exec(
        select(Meeting).where(
            Meeting.group_id == group_id, Meeting.title == "Default Meeting"
        )
    ).first()

    if not default_meeting:
        now = datetime.utcnow()
        default_meeting = Meeting(
            group_id=group_id,
            title="Default Meeting",
            description="Auto-created meeting for uploaded photos",
            start_time=now,
            end_time=now,
            meeting_date=now.date(),
            photo_count=0,
            participant_count=0,
        )
        db.add(default_meeting)
        db.commit()
        db.refresh(default_meeting)

    # Create photo record
    photo = Photo(
        group_id=group_id,
        uploader_id=current_user.id,
        meeting_id=default_meeting.id,
        filename_orig=filename,
        file_size=file.size or 0,
        file_hash="",  # Will be calculated by worker
        mime_type=file.content_type or "application/octet-stream",
        is_processed=False,
    )

    db.add(photo)
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
    return photos


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

    # TODO: Add proper authorization check based on group membership

    return photo


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

    # TODO: Add proper authorization check based on group membership
    
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
