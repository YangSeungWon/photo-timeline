from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func

from ..core.database import get_db
from ..core.deps import get_current_active_user
from ..models.user import User
from ..models.group import Group
from ..models.membership import Membership, MembershipRole, MembershipStatus
from ..schemas.group import GroupCreate, GroupResponse, GroupJoinRequest

router = APIRouter()


@router.post("", response_model=GroupResponse)
async def create_group(
    group_data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new group."""
    # Create group
    group = Group(
        name=group_data.name,
        description=group_data.description,
        is_private=group_data.is_private,
        created_by=current_user.id,
    )

    db.add(group)
    db.commit()
    db.refresh(group)

    # Add creator as owner
    membership = Membership(
        user_id=current_user.id,
        group_id=group.id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )

    db.add(membership)
    db.commit()

    # Return group with member count
    group_response = GroupResponse.model_validate(group)
    group_response.member_count = 1

    return group_response


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get group information."""
    # Find group
    group = db.exec(select(Group).where(Group.id == group_id)).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Check if user is a member (for private groups)
    membership = db.exec(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.group_id == group_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()

    if group.is_private and not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to private group",
        )

    # Get member count
    member_count = db.exec(
        select(func.count(Membership.id)).where(
            Membership.group_id == group_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    ).first()

    group_response = GroupResponse.model_validate(group)
    group_response.member_count = member_count or 0

    return group_response


@router.post("/{group_id}/join", response_model=dict)
async def join_group(
    group_id: UUID,
    join_data: GroupJoinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Join a group."""
    # Find group
    group = db.exec(select(Group).where(Group.id == group_id)).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # Check if already a member
    existing_membership = db.exec(
        select(Membership).where(
            Membership.user_id == current_user.id, Membership.group_id == group_id
        )
    ).first()

    if existing_membership:
        if existing_membership.status == MembershipStatus.ACTIVE:
            return {"message": "Already a member of this group"}
        elif existing_membership.status == MembershipStatus.PENDING:
            return {"message": "Join request already pending"}
        elif existing_membership.status == MembershipStatus.BANNED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are banned from this group",
            )

    # Create membership
    if group.is_private:
        # Private groups require approval
        status = MembershipStatus.PENDING
        message = "Join request sent. Waiting for approval."
    else:
        # Public groups allow immediate joining
        status = MembershipStatus.ACTIVE
        message = "Successfully joined the group!"

    membership = Membership(
        user_id=current_user.id,
        group_id=group_id,
        role=MembershipRole.MEMBER,
        status=status,
    )

    db.add(membership)
    db.commit()

    return {"message": message}
