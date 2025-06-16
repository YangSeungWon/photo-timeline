from datetime import datetime
from uuid import UUID
from typing import Dict, Any
from pydantic import BaseModel


class PhotoResponse(BaseModel):
    """Photo response model."""

    id: UUID
    meeting_id: UUID | None
    filename: str
    file_path: str
    taken_at: datetime | None
    gps_latitude: float | None
    gps_longitude: float | None
    exif_data: Dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PhotoUploadResponse(BaseModel):
    """Photo upload response."""

    id: UUID
    filename: str
    status: str = "uploaded"
    message: str = "Photo uploaded successfully"
