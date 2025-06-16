from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional


class Meeting(SQLModel, table=True):
    """Meeting model representing a cluster of photos taken around the same time."""

    model_config = {"arbitrary_types_allowed": True}

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Group association
    group_id: UUID = Field(foreign_key="group.id", index=True)

    # Meeting metadata
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Time range (automatically calculated from photos)
    start_time: datetime
    end_time: datetime
    meeting_date: datetime  # Primary date for grouping (usually start_time date)

    # Location data
    # GPS track as LineString for the meeting route
    track_gps: Optional[WKTElement] = Field(
        default=None, sa_column=Column(Geometry("LINESTRING", srid=4326), nullable=True)
    )

    # Bounding box for the meeting area
    bbox_north: Optional[float] = Field(default=None)
    bbox_south: Optional[float] = Field(default=None)
    bbox_east: Optional[float] = Field(default=None)
    bbox_west: Optional[float] = Field(default=None)

    # Statistics
    photo_count: int = Field(default=0)
    participant_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Cover photo for the meeting
    cover_photo_id: Optional[UUID] = Field(default=None, foreign_key="photo.id")
