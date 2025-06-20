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
        """Convert Photo model to PhotoResponse with GPS coordinate handling."""
        # Convert all basic fields from the Photo model
        data = {}
        for field_name in cls.__fields__.keys():
            if hasattr(photo, field_name):
                value = getattr(photo, field_name)
                # Convert UUID to string for JSON serialization
                if hasattr(value, 'hex'):  # UUID check
                    data[field_name] = str(value)
                else:
                    data[field_name] = value
        
        # Handle PostGIS point_gps field for GPS coordinates
        logger.info(f"Processing GPS data for photo {photo.id}")
        logger.info(f"Raw point_gps: {photo.point_gps}")
        logger.info(f"Has point_gps attr: {hasattr(photo, 'point_gps')}")
        
        if hasattr(photo, 'point_gps') and photo.point_gps:
            try:
                # Use geoalchemy2.shape.to_shape() for clean WKBElement → shapely Point conversion
                from geoalchemy2.shape import to_shape
                import json
                
                point = to_shape(photo.point_gps)  # shapely.geometry.Point
                data['gps_latitude'] = float(point.y)   # lat
                data['gps_longitude'] = float(point.x)  # lng
                
                logger.info(f"Successfully parsed GPS for photo {photo.id}: lat={point.y}, lng={point.x}")
                
                # Create GeoJSON format for frontend (not WKT)
                geojson = {
                    "type": "Point",
                    "coordinates": [point.x, point.y]  # [lng, lat] order in GeoJSON
                }
                data['point_gps'] = json.dumps(geojson)  # JSON string for frontend
                
                logger.info(f"Generated GeoJSON for photo {photo.id}: {data['point_gps']}")
                
            except Exception as e:
                logger.warning(f"Failed to parse GPS coordinates using to_shape for photo {photo.id}: {e}")
                # Fallback to string conversion
                try:
                    point_str = str(photo.point_gps)
                    logger.info(f"Trying fallback string parsing for photo {photo.id}: {point_str}")
                    
                    if point_str and point_str.startswith('POINT('):
                        # Parse WKT format: "POINT(longitude latitude)"
                        coords_str = point_str.replace('POINT(', '').replace(')', '')
                        coords = coords_str.split()
                        if len(coords) >= 2:
                            lng = float(coords[0])
                            lat = float(coords[1])
                            data['gps_longitude'] = lng
                            data['gps_latitude'] = lat
                            
                            logger.info(f"Fallback parsing successful for photo {photo.id}: lat={lat}, lng={lng}")
                            
                            # Create GeoJSON fallback
                            geojson = {
                                "type": "Point", 
                                "coordinates": [lng, lat]
                            }
                            data['point_gps'] = json.dumps(geojson)
                        else:
                            logger.warning(f"Invalid coordinate format for photo {photo.id}: {coords}")
                            data['gps_latitude'] = None
                            data['gps_longitude'] = None
                            data['point_gps'] = None
                    else:
                        logger.warning(f"Invalid WKT format for photo {photo.id}: {point_str}")
                        data['gps_latitude'] = None
                        data['gps_longitude'] = None
                        data['point_gps'] = None
                except Exception as e2:
                    logger.error(f"Complete GPS parsing failure for photo {photo.id}: {e2}")
                    data['point_gps'] = None
                    data['gps_latitude'] = None
                    data['gps_longitude'] = None
        else:
            logger.info(f"No GPS data available for photo {photo.id}")
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
