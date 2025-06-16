from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional


class User(SQLModel, table=True):
    """User model for authentication and profile management."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str = Field(max_length=100)

    # Authentication
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    last_login: Optional[datetime] = Field(default=None)

    # Profile
    avatar_filename: Optional[str] = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=50)
