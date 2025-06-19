import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from sqlmodel import Session, select
from geoalchemy2.shape import to_shape

from .core.database import engine
from .core.thumbs import create_thumbnail
from .models.photo import Photo
from .models.meeting import Meeting
from .models.group import Group
from photo_core import extract_exif, cluster_photos_into_meetings

logger = logging.getLogger(__name__)


def serialize_exif_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert EXIF data to JSON-serializable format."""
    serialized = {}
    
    for key, value in data.items():
        if isinstance(value, datetime):
            # Convert datetime to ISO format string
            serialized[key] = value.isoformat()
        elif isinstance(value, (list, tuple)):
            # Handle lists/tuples recursively
            serialized[key] = [
                item.isoformat() if isinstance(item, datetime) else item
                for item in value
            ]
        elif isinstance(value, dict):
            # Handle nested dictionaries recursively
            serialized[key] = serialize_exif_data(value)
        elif hasattr(value, '__dict__'):
            # Handle objects with attributes (like Point objects)
            try:
                serialized[key] = str(value)
            except:
                serialized[key] = None
        else:
            # Keep primitive types as-is
            try:
                # Test if value is JSON serializable
                json.dumps(value)
                serialized[key] = value
            except (TypeError, ValueError):
                # If not serializable, convert to string
                serialized[key] = str(value) if value is not None else None
    
    return serialized


def process_photo(photo_id: str, file_path: str) -> bool:
    """
    Process a photo through the complete pipeline:
    1. Extract EXIF data and update photo record
    2. Trigger meeting clustering for the group
    3. Generate thumbnail

    Args:
        photo_id: UUID of the photo to process
        file_path: Absolute path to the uploaded file

    Returns:
        True if processing succeeded, False otherwise
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return False

    try:
        with Session(engine) as session:
            # Get the photo record
            photo = session.get(Photo, photo_id)
            if not photo:
                logger.error(f"Photo {photo_id} not found in database")
                return False

            logger.info(f"Processing photo {photo_id}: {file_path}")

            # Step 1: Extract EXIF data
            success = _extract_exif_data(session, photo, file_path)
            if not success:
                logger.warning(f"EXIF extraction failed for {photo_id}")

            # Step 2: Trigger meeting clustering for the group
            # This will assign the photo to a meeting based on its timestamp
            _cluster_group_photos(session, str(photo.group_id))

            # Step 3: Generate thumbnail
            _generate_thumbnail(session, photo, file_path)

            # Mark photo as processed
            photo.is_processed = True
            session.add(photo)

            # Final commit
            session.commit()
            logger.info(f"Successfully processed photo {photo_id}")
            return True

    except Exception as e:
        logger.error(f"Error processing photo {photo_id}: {e}")
        return False


def _extract_exif_data(session: Session, photo: Photo, file_path: Path) -> bool:
    """Extract EXIF data and update photo record."""
    try:
        metadata = extract_exif(file_path)

        # Serialize EXIF data for JSON storage
        serialized_metadata = serialize_exif_data(metadata)
        photo.exif_data = serialized_metadata

        # Set taken_at from EXIF datetime
        if "DateTimeOriginal" in metadata:
            photo.shot_at = metadata["DateTimeOriginal"]

        # Set GPS location if available
        if "GPSLat" in metadata and "GPSLong" in metadata:
            lat = metadata["GPSLat"]
            lon = metadata["GPSLong"]
            if lat is not None and lon is not None:
                # Convert to PostGIS format (longitude first, then latitude)
                photo.point_gps = f"POINT({lon} {lat})"

        session.add(photo)
        logger.info(f"Extracted EXIF data for photo {photo.id}")
        return True

    except Exception as e:
        logger.error(f"EXIF extraction failed for photo {photo.id}: {e}")
        return False


def _cluster_group_photos(session: Session, group_id: str) -> bool:
    """Trigger photo clustering for the entire group."""
    try:
        # Get all photos in the group that have shot_at timestamps
        stmt = (
            select(Photo)
            .where(Photo.group_id == group_id)
            .where(Photo.shot_at.is_not(None))
        )
        photos = session.exec(stmt).all()

        if len(photos) < 2:
            logger.info(f"Not enough photos for clustering in group {group_id}")
            return True

        # Convert photos to dictionary format expected by photo_core
        photo_dicts = []
        for photo in photos:
            photo_dict = {
                "id": str(photo.id),
                "DateTimeOriginal": photo.shot_at,
                "group_id": str(photo.group_id),
            }
            photo_dicts.append(photo_dict)

        # Use photo_core clustering
        clustered_photos = cluster_photos_into_meetings(photo_dicts)
        
        # Group clustered photos by meeting_id to create meetings
        meetings_data = {}
        for clustered_photo in clustered_photos:
            meeting_id = clustered_photo.get("meeting_id")
            if meeting_id:
                if meeting_id not in meetings_data:
                    meetings_data[meeting_id] = {
                        "photos": [],
                        "start_time": clustered_photo["DateTimeOriginal"],
                        "end_time": clustered_photo["DateTimeOriginal"],
                        "meeting_date": clustered_photo["meeting_date"]
                    }
                
                meetings_data[meeting_id]["photos"].append(clustered_photo)
                # Update time range
                photo_time = clustered_photo["DateTimeOriginal"]
                if photo_time < meetings_data[meeting_id]["start_time"]:
                    meetings_data[meeting_id]["start_time"] = photo_time
                if photo_time > meetings_data[meeting_id]["end_time"]:
                    meetings_data[meeting_id]["end_time"] = photo_time

        # Create or update meetings
        for meeting_id, meeting_data in meetings_data.items():
            meeting = session.get(Meeting, meeting_id)
            if not meeting:
                meeting = Meeting(
                    id=meeting_id,
                    group_id=group_id,
                    title=f"Meeting {meeting_data['meeting_date']}",
                    start_time=meeting_data["start_time"],
                    end_time=meeting_data["end_time"],
                    meeting_date=meeting_data["meeting_date"],
                    photo_count=len(meeting_data["photos"])
                )
                session.add(meeting)
            else:
                # Update existing meeting
                meeting.start_time = meeting_data["start_time"]
                meeting.end_time = meeting_data["end_time"]
                meeting.photo_count = len(meeting_data["photos"])
                session.add(meeting)

        # Update photos with meeting assignments
        for clustered_photo in clustered_photos:
            photo_id = clustered_photo["id"]
            meeting_id = clustered_photo.get("meeting_id")
            
            photo = session.get(Photo, photo_id)
            if photo:
                photo.meeting_id = meeting_id
                session.add(photo)

        session.commit()
        logger.info(f"Clustered photos for group {group_id}")
        return True

    except Exception as e:
        logger.error(f"Photo clustering failed for group {group_id}: {e}")
        return False


def _generate_thumbnail(session: Session, photo: Photo, file_path: Path) -> bool:
    """Generate thumbnail for the photo."""
    try:
        thumb_path = create_thumbnail(file_path)

        if thumb_path:
            # Store relative path from upload directory
            photo.filename_thumb = str(thumb_path.name)
            session.add(photo)
            logger.info(f"Generated thumbnail for photo {photo.id}")
            return True
        else:
            logger.warning(f"Thumbnail generation failed for photo {photo.id}")
            return False

    except Exception as e:
        logger.error(f"Thumbnail generation error for photo {photo.id}: {e}")
        return False


def cleanup_failed_upload(photo_id: str, file_path: str) -> bool:
    """
    Clean up a failed upload by removing the file and database record.

    Args:
        photo_id: UUID of the photo to clean up
        file_path: Path to the file to remove

    Returns:
        True if cleanup succeeded
    """
    try:
        # Remove file if it exists
        file_path = Path(file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Removed file: {file_path}")

        # Remove database record
        with Session(engine) as session:
            photo = session.get(Photo, photo_id)
            if photo:
                session.delete(photo)
                session.commit()
                logger.info(f"Removed photo record: {photo_id}")

        return True

    except Exception as e:
        logger.error(f"Cleanup failed for photo {photo_id}: {e}")
        return False
