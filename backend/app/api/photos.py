from uuid import UUID
from typing import List
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
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
        default_meeting = Meeting(
            group_id=group_id,
            title="Default Meeting",
            description="Auto-created meeting for uploaded photos",
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
    group_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List photos in a group."""
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

    # Get photos (for now, we'll get all photos since we don't have group association yet)
    # TODO: Add group_id to Photo model or use Meeting relationship
    photos = db.exec(select(Photo).offset(offset).limit(limit)).all()

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
