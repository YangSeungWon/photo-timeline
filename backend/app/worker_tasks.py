import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from sqlmodel import Session, select
from geoalchemy2.shape import to_shape
import redis
import time

from .core.database import engine
from .core.thumbs import create_thumbnail
from .core.queues import default_queue
from .models.photo import Photo
from .models.meeting import Meeting
from .models.group import Group
from photo_core import extract_exif, cluster_photos_into_meetings

logger = logging.getLogger(__name__)

# Redis connection for clustering coordination
try:
    import os
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_db = int(os.getenv("REDIS_DB", 0))
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
except Exception:
    redis_client = None

# Clustering delay settings
CLUSTERING_DELAY_SECONDS = 30  # Wait 30 seconds before clustering


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

            # Step 2: Schedule delayed clustering for the group (avoid O(n²) complexity)
            _schedule_group_clustering(str(photo.group_id))

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
        # Create a savepoint for clustering operations
        savepoint = session.begin_nested()
        # Get all photos in the group that have shot_at timestamps
        stmt = (
            select(Photo)
            .where(Photo.group_id == group_id)
            .where(Photo.shot_at.is_not(None))
        )
        photos = session.exec(stmt).all()

        if len(photos) == 0:
            logger.info(f"No photos with timestamps in group {group_id}")
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
        
        # Get existing meetings in the group (excluding default meeting)
        existing_meetings = session.exec(
            select(Meeting)
            .where(Meeting.group_id == group_id)
            .where(Meeting.title != "Default Meeting")
        ).all()
        existing_meetings_by_date = {m.meeting_date: m for m in existing_meetings}
        
        # Clean approach: Move photos to Default Meeting first, then delete auto-generated meetings
        # (Keep only Default Meeting and manually created meetings)
        
        # Get or create Default Meeting
        default_meeting = session.exec(
            select(Meeting).where(
                Meeting.group_id == group_id, 
                Meeting.title == "Default Meeting"
            )
        ).first()
        
        if not default_meeting:
            from datetime import datetime
            now = datetime.utcnow()
            default_meeting = Meeting(
                group_id=group_id,
                title="Default Meeting",
                description="Auto-created meeting for uploaded photos",
                start_time=now,
                end_time=now,
                meeting_date=now.date(),
                photo_count=0,
                participant_count=0,
            )
            session.add(default_meeting)
            session.flush()
        
        # Move all photos to Default Meeting first (to avoid FK constraint violations)
        photos_in_group = session.exec(
            select(Photo).where(Photo.group_id == group_id)
        ).all()
        
        for photo in photos_in_group:
            photo.meeting_id = default_meeting.id
            session.add(photo)
        session.flush()
        
        # Now safely delete auto-generated meetings
        auto_meetings = session.exec(
            select(Meeting)
            .where(Meeting.group_id == group_id)
            .where(Meeting.title.like("Meeting %"))  # Auto-generated meetings
        ).all()
        
        for auto_meeting in auto_meetings:
            session.delete(auto_meeting)
        session.flush()

        # Group clustered photos by meeting date
        meetings_data = {}
        for clustered_photo in clustered_photos:
            meeting_date = clustered_photo.get("meeting_date")
            if meeting_date:
                if meeting_date not in meetings_data:
                    meetings_data[meeting_date] = {
                        "photos": [],
                        "start_time": clustered_photo["DateTimeOriginal"],
                        "end_time": clustered_photo["DateTimeOriginal"],
                    }
                
                meetings_data[meeting_date]["photos"].append(clustered_photo)
                # Update time range
                photo_time = clustered_photo["DateTimeOriginal"]
                if photo_time < meetings_data[meeting_date]["start_time"]:
                    meetings_data[meeting_date]["start_time"] = photo_time
                if photo_time > meetings_data[meeting_date]["end_time"]:
                    meetings_data[meeting_date]["end_time"] = photo_time

        # Create new meetings based on clustered data
        for meeting_date, meeting_data in meetings_data.items():
            meeting = Meeting(
                group_id=group_id,
                title=f"Meeting {meeting_date}",
                start_time=meeting_data["start_time"],
                end_time=meeting_data["end_time"],
                meeting_date=meeting_date,
                photo_count=len(meeting_data["photos"]),
                participant_count=0,
            )
            session.add(meeting)
            session.flush()  # Get the ID
            
            # Assign photos to this meeting
            for clustered_photo in meeting_data["photos"]:
                photo_id = clustered_photo["id"]
                photo = session.get(Photo, photo_id)
                if photo:
                    photo.meeting_id = meeting.id
                    session.add(photo)

        # Commit the savepoint and then the main transaction
        savepoint.commit()
        session.commit()
        logger.info(f"Clustered {len(photos)} photos into {len(meetings_data)} meetings for group {group_id}")
        return True

    except Exception as e:
        logger.error(f"Photo clustering failed for group {group_id}: {e}")
        # Rollback to savepoint to avoid session corruption
        try:
            savepoint.rollback()
        except:
            session.rollback()
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


def _schedule_group_clustering(group_id: str) -> None:
    """
    Schedule delayed clustering for a group to avoid O(n²) complexity.
    Uses Redis to track when the last photo was processed and delays clustering.
    """
    if not redis_client:
        # Fallback to immediate clustering if Redis is not available
        logger.warning("Redis not available, falling back to immediate clustering")
        try:
            with Session(engine) as session:
                _cluster_group_photos(session, group_id)
        except Exception as e:
            logger.error(f"Immediate clustering failed for group {group_id}: {e}")
        return

    try:
        # Set timestamp for when this group last had a photo processed
        current_time = int(time.time())
        key = f"clustering_schedule:{group_id}"
        
        # Set expiration time for the key (prevents memory leak)
        redis_client.setex(key, CLUSTERING_DELAY_SECONDS + 60, current_time)
        
        # Schedule clustering job with delay (will be deduplicated by RQ)
        delay_seconds = CLUSTERING_DELAY_SECONDS
        job = default_queue.enqueue_in(
            delay_seconds,
            cluster_group_if_ready,
            group_id=group_id,
            scheduled_time=current_time,
            job_id=f"cluster_{group_id}_{current_time}",  # Unique job ID
            job_timeout=300,
        )
        
        logger.info(f"Scheduled clustering for group {group_id} in {delay_seconds} seconds")
        
    except Exception as e:
        logger.error(f"Failed to schedule clustering for group {group_id}: {e}")
        # Fallback to immediate clustering
        try:
            with Session(engine) as session:
                _cluster_group_photos(session, group_id)
        except Exception as e2:
            logger.error(f"Fallback clustering failed for group {group_id}: {e2}")


def cluster_group_if_ready(group_id: str, scheduled_time: int) -> bool:
    """
    Execute clustering only if no newer photos have been processed since scheduling.
    This prevents redundant clustering when multiple photos are uploaded rapidly.
    """
    if not redis_client:
        logger.warning("Redis not available for clustering coordination")
        try:
            with Session(engine) as session:
                return _cluster_group_photos(session, group_id)
        except Exception as e:
            logger.error(f"Clustering failed for group {group_id}: {e}")
            return False

    try:
        key = f"clustering_schedule:{group_id}"
        latest_time = redis_client.get(key)
        
        if latest_time is None:
            logger.info(f"No pending photos for group {group_id}, skipping clustering")
            return True
            
        latest_time = int(latest_time)
        
        # Only cluster if this is the most recent scheduling
        if latest_time <= scheduled_time:
            logger.info(f"Executing clustering for group {group_id}")
            # Clear the scheduling key to prevent duplicate clustering
            redis_client.delete(key)
            
            with Session(engine) as session:
                return _cluster_group_photos(session, group_id)
        else:
            logger.info(f"Skipping clustering for group {group_id} - newer photos detected")
            return True
            
    except Exception as e:
        logger.error(f"Error in cluster_group_if_ready for group {group_id}: {e}")
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
