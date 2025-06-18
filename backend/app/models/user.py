from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional


class User(SQLModel, table=True):
    """User model for authentication and profile management."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    display_name: str = Field(max_length=100)

    # Authentication
    hashed_password: str
    is_active: bool = Field(default=False)  # User starts inactive until email verified
    is_superuser: bool = Field(default=False)

    # Email verification
    email_verified: bool = Field(default=False)
    email_verification_token: Optional[str] = Field(default=None, max_length=255)
    email_verification_expires: Optional[datetime] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(default=None)

    # Profile
    avatar_filename: Optional[str] = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", max_length=50)
