from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class MeetingResponse(BaseModel):
    """Meeting response model."""

    id: UUID
    group_id: UUID
    title: Optional[str]
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    meeting_date: datetime
    track_gps: Optional[str]  # WKT string representation
    bbox_north: Optional[float]
    bbox_south: Optional[float]
    bbox_east: Optional[float]
    bbox_west: Optional[float]
    photo_count: int
    participant_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    cover_photo_id: Optional[UUID]

    class Config:
        from_attributes = True


class MeetingCreate(BaseModel):
    """Meeting creation request."""

    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    track_gps: bool = False 