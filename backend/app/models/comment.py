from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional


class Comment(SQLModel, table=True):
    """Comment model for threaded discussions on photos."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Associations
    photo_id: UUID = Field(foreign_key="photo.id", index=True)
    author_id: UUID = Field(foreign_key="user.id", index=True)

    # Threading support
    parent_id: Optional[UUID] = Field(default=None, foreign_key="comment.id")
    thread_root_id: Optional[UUID] = Field(
        default=None, foreign_key="comment.id", index=True
    )
    depth: int = Field(default=0)  # Nesting level (0 = top-level comment)

    # Comment content
    content: str = Field(sa_column=Column(Text))

    # Moderation
    is_edited: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    is_flagged: bool = Field(default=False)
    flagged_reason: Optional[str] = Field(default=None, max_length=200)

    # Engagement metrics
    like_count: int = Field(default=0)
    reply_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)

    # Sorting and display
    sort_order: int = Field(default=0)  # For custom ordering within threads
