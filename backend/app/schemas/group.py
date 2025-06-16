from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class GroupCreate(BaseModel):
    """Group creation request."""

    name: str
    description: str | None = None
    is_private: bool = False


class GroupResponse(BaseModel):
    """Group response model."""

    id: UUID
    name: str
    description: str | None
    is_private: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    member_count: int | None = None

    class Config:
        from_attributes = True


class GroupJoinRequest(BaseModel):
    """Group join request."""

    pass  # No additional data needed for now
