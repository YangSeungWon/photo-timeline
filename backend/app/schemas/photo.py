from datetime import datetime
from uuid import UUID
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, computed_field
import logging

logger = logging.getLogger(__name__)


class PhotoResponse(BaseModel):
    """Photo response model."""

    id: UUID
    group_id: UUID
    uploader_id: UUID
    meeting_id: Optional[UUID] = None
    
    # File information
    filename_orig: str
    filename_thumb: Optional[str] = None
    filename_medium: Optional[str] = None
    file_size: int
    file_hash: str
    mime_type: str
    
    # Photo metadata
    shot_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens_model: Optional[str] = None
    
    # Image dimensions
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[int] = None
    
    # Camera settings
    aperture: Optional[float] = None
    shutter_speed: Optional[str] = None
    iso: Optional[int] = None
    focal_length: Optional[float] = None
    flash: Optional[bool] = None
    
    # GPS data - PostGIS point as string and computed coordinates
    point_gps: Optional[str] = None  # WKT string for frontend compatibility
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    
    # Raw EXIF data
    exif_data: Optional[Dict[str, Any]] = None
    
    # User annotations
    caption: Optional[str] = None
    tags: Optional[str] = None
    
    # Processing status
    is_processed: bool = False
    processing_error: Optional[str] = None
    
    # Timestamps
    uploaded_at: datetime
    updated_at: Optional[datetime] = None
    
    # Privacy
    is_public: bool = True
    is_flagged: bool = False
    flagged_reason: Optional[str] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_photo_model(cls, photo):
        """Create PhotoResponse from Photo model, handling PostGIS conversion."""
        # Start with basic fields
        data = {
            'id': photo.id,
            'group_id': photo.group_id,
            'uploader_id': photo.uploader_id,
            'meeting_id': photo.meeting_id,
            'filename_orig': photo.filename_orig,
            'filename_thumb': photo.filename_thumb,
            'filename_medium': photo.filename_medium,
            'file_size': photo.file_size,
            'file_hash': photo.file_hash,
            'mime_type': photo.mime_type,
            'shot_at': photo.shot_at,
            'camera_make': photo.camera_make,
            'camera_model': photo.camera_model,
            'lens_model': photo.lens_model,
            'width': photo.width,
            'height': photo.height,
            'orientation': photo.orientation,
            'aperture': photo.aperture,
            'shutter_speed': photo.shutter_speed,
            'iso': photo.iso,
            'focal_length': photo.focal_length,
            'flash': photo.flash,
            'gps_altitude': photo.gps_altitude,
            'gps_accuracy': photo.gps_accuracy,
            'exif_data': photo.exif_data,
            'caption': photo.caption,
            'tags': photo.tags,
            'is_processed': photo.is_processed,
            'processing_error': photo.processing_error,
            'uploaded_at': photo.uploaded_at,
            'updated_at': photo.updated_at,
            'is_public': photo.is_public,
            'is_flagged': photo.is_flagged,
            'flagged_reason': photo.flagged_reason,
        }
        
        # Handle PostGIS point_gps field for GPS coordinates
        if hasattr(photo, 'point_gps') and photo.point_gps:
            try:
                # Convert PostGIS point to lat/lon and store WKT string
                point_str = str(photo.point_gps)
                data['point_gps'] = point_str  # Store WKT string for frontend
                
                if point_str and point_str.startswith('POINT('):
                    # Parse WKT format: "POINT(longitude latitude)"
                    coords_str = point_str.replace('POINT(', '').replace(')', '')
                    coords = coords_str.split()
                    if len(coords) >= 2:
                        data['gps_longitude'] = float(coords[0])
                        data['gps_latitude'] = float(coords[1])
                    else:
                        data['gps_latitude'] = None
                        data['gps_longitude'] = None
                else:
                    data['gps_latitude'] = None
                    data['gps_longitude'] = None
            except Exception as e:
                logger.warning(f"Failed to parse GPS coordinates for photo {photo.id}: {e}")
                data['point_gps'] = None
                data['gps_latitude'] = None
                data['gps_longitude'] = None
        else:
            data['point_gps'] = None
            data['gps_latitude'] = None
            data['gps_longitude'] = None
            
        return cls(**data)


class PhotoUploadResponse(BaseModel):
    """Photo upload response."""

    id: UUID
    filename: str
    status: str = "uploaded"
    message: str = "Photo uploaded successfully"
