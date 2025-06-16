from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from enum import Enum


class MembershipRole(str, Enum):
    """Membership roles within a group."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    PENDING = "pending"


class MembershipStatus(str, Enum):
    """Membership status."""

    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    LEFT = "left"


class Membership(SQLModel, table=True):
    """Membership model for user-group relationships."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Foreign keys
    user_id: UUID = Field(foreign_key="user.id")
    group_id: UUID = Field(foreign_key="group.id")

    # Membership details
    role: MembershipRole = Field(default=MembershipRole.MEMBER)
    status: MembershipStatus = Field(default=MembershipStatus.PENDING)

    # Timestamps
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = Field(default=None)
    left_at: Optional[datetime] = Field(default=None)

    # Approval tracking
    approved_by: Optional[UUID] = Field(default=None, foreign_key="user.id")

    # Unique constraint on user-group combination
    __table_args__ = ({"sqlite_autoincrement": True},)
