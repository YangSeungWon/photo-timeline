from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """User response model."""

    id: UUID
    email: EmailStr
    display_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
