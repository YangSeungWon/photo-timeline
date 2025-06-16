from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional


class Group(SQLModel, table=True):
    """Group model for organizing users into photo-sharing communities."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100, index=True)
    description: Optional[str] = Field(default=None, max_length=500)

    # Group settings
    is_private: bool = Field(default=True)
    require_approval: bool = Field(default=True)
    max_members: Optional[int] = Field(default=None)

    # Ownership
    owner_id: UUID = Field(foreign_key="user.id")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Group image
    cover_photo_filename: Optional[str] = Field(default=None, max_length=255)
