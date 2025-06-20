from uuid import UUID
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select

from ..core.database import get_db
from ..core.deps import get_current_active_user
from ..models.user import User
from ..models.group import Group
from ..models.meeting import Meeting
from ..models.membership import Membership, MembershipStatus
from ..schemas.meeting import MeetingResponse, MeetingCreate
from ..worker_tasks import cleanup_empty_meetings

router = APIRouter()


@router.get("", response_model=List[MeetingResponse])
async def list_meetings(
    group_id: Optional[UUID] = Query(None, description="Filter by group ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List meetings in a group."""
    if not group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="group_id is required"
        )
    
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

    # Get meetings
    meetings = db.exec(
        select(Meeting)
        .where(Meeting.group_id == group_id)
        .order_by(Meeting.start_time.desc())
    ).all()

    return meetings


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific meeting."""
    meeting = db.exec(select(Meeting).where(Meeting.id == meeting_id)).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )

    # Check membership to the group
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

    return meeting


@router.post("", response_model=MeetingResponse)
async def create_meeting(
    meeting_data: MeetingCreate,
    group_id: UUID = Query(..., description="Group ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new meeting."""
    # Verify group access
    group = db.exec(select(Group).where(Group.id == group_id)).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Check membership (only members can create meetings)
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

    # Create meeting
    meeting = Meeting(
        group_id=group_id,
        title=meeting_data.title,
        description=meeting_data.description,
        start_time=meeting_data.start_time,
        end_time=meeting_data.end_time,
        meeting_date=meeting_data.start_time.date(),
        track_gps=None,  # Will be set when GPS data is available
        photo_count=0,
        participant_count=1,  # Creator is first participant
    )

    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return meeting


@router.post("/cleanup-empty/{group_id}")
async def cleanup_empty_meetings_in_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Clean up empty meetings in a group (admin action)."""
    # Verify group access
    group = db.exec(select(Group).where(Group.id == group_id)).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Check if user is admin of the group
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

    # For now, any group member can cleanup empty meetings
    # TODO: Add role-based permissions if needed
    
    try:
        deleted_count = cleanup_empty_meetings(db, str(group_id))
        db.commit()
        
        return {
            "message": f"Successfully cleaned up {deleted_count} empty meetings",
            "deleted_count": deleted_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup empty meetings: {str(e)}"
        ) 