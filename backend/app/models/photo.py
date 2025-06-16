from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, JSON
from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, Dict, Any


class Photo(SQLModel, table=True):
    """Photo model with EXIF data and GPS support."""

    model_config = {"arbitrary_types_allowed": True}

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Associations
    group_id: UUID = Field(foreign_key="group.id", index=True)
    uploader_id: UUID = Field(foreign_key="user.id", index=True)
    meeting_id: Optional[UUID] = Field(
        default=None, foreign_key="meeting.id", index=True
    )

    # File information
    filename_orig: str = Field(max_length=255)
    filename_thumb: Optional[str] = Field(default=None, max_length=255)
    filename_medium: Optional[str] = Field(default=None, max_length=255)
    file_size: int  # Size in bytes
    file_hash: str = Field(max_length=64, index=True)  # SHA-256 hash for deduplication
    mime_type: str = Field(max_length=100)

    # Photo metadata from EXIF
    shot_at: Optional[datetime] = Field(default=None, index=True)
    camera_make: Optional[str] = Field(default=None, max_length=100)
    camera_model: Optional[str] = Field(default=None, max_length=100)
    lens_model: Optional[str] = Field(default=None, max_length=100)

    # Image dimensions
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    orientation: Optional[int] = Field(default=None)  # EXIF orientation

    # Camera settings
    aperture: Optional[float] = Field(default=None)
    shutter_speed: Optional[str] = Field(default=None, max_length=20)
    iso: Optional[int] = Field(default=None)
    focal_length: Optional[float] = Field(default=None)
    flash: Optional[bool] = Field(default=None)

    # GPS data - PostGIS Point geometry
    point_gps: Optional[WKTElement] = Field(
        default=None, sa_column=Column(Geometry("POINT", srid=4326), nullable=True)
    )
    gps_altitude: Optional[float] = Field(default=None)
    gps_accuracy: Optional[float] = Field(default=None)  # Accuracy in meters

    # Raw EXIF data as JSON for extensibility
    exif_data: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )

    # User annotations
    caption: Optional[str] = Field(default=None, sa_column=Column(Text))
    tags: Optional[str] = Field(default=None, max_length=500)  # Comma-separated tags

    # Processing status
    is_processed: bool = Field(default=False)
    processing_error: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Timestamps
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: Optional[datetime] = Field(default=None)

    # Privacy and moderation
    is_public: bool = Field(default=True)
    is_flagged: bool = Field(default=False)
    flagged_reason: Optional[str] = Field(default=None, max_length=200)
