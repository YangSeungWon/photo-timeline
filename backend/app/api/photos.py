from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlmodel import Session, select

from ..core.database import get_db
from ..core.deps import get_current_active_user
from ..core.storage import save_upload_file
from ..models.user import User
from ..models.group import Group
from ..models.membership import Membership, MembershipStatus
from ..models.photo import Photo
from ..schemas.photo import PhotoResponse, PhotoUploadResponse

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

    # Create photo record
    photo = Photo(
        filename=filename,
        file_path=file_path,
        # Note: EXIF processing will be done by background worker
        # For now, we just store the basic info
    )

    db.add(photo)
    db.commit()
    db.refresh(photo)

    # TODO: Enqueue background task for EXIF extraction and clustering

    return PhotoUploadResponse(
        id=photo.id,
        filename=filename,
        status="uploaded",
        message="Photo uploaded successfully. Processing in background.",
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
