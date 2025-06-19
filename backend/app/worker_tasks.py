import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from sqlmodel import Session, select
from sqlalchemy import text
from geoalchemy2.shape import to_shape
import redis
import time

from .core.database import engine
from .core.thumbs import create_thumbnail
from .core.queues import default_queue
from .core.config import settings
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

            # Step 2: Incremental clustering - attach photo to appropriate meeting
            _attach_incremental(session, photo)

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


def _attach_incremental(session: Session, photo: Photo) -> bool:
    """
    Incremental clustering based on user's design:
    1. Check if photo's shot_at falls within existing meeting range
    2. If not, find closest meeting within MEETING_GAP
    3. If still no match, create new meeting
    
    Uses FOR UPDATE for concurrency control.
    """
    if not photo.shot_at:
        logger.info(f"Photo {photo.id} has no timestamp, keeping in Default Meeting")
        return True
        
    try:
        # Get MEETING_GAP from settings
        meeting_gap_hours = settings.MEETING_GAP_HOURS
        meeting_gap = timedelta(hours=meeting_gap_hours)
        
        # Step 1: Find if photo's shot_at is contained within existing meeting time range
        contained_meeting = session.exec(
            text("""
                SELECT * FROM meeting 
                WHERE group_id = :group_id 
                AND title != 'Default Meeting'
                AND :shot_at BETWEEN start_time AND end_time
                ORDER BY start_time DESC
                LIMIT 1
                FOR UPDATE
            """).bindparam(
                group_id=str(photo.group_id),
                shot_at=photo.shot_at
            )
        ).first()
        
        if contained_meeting:
            # Convert to Meeting object
            meeting = session.get(Meeting, contained_meeting.id)
            if meeting:
                # Update default meeting count (remove from default)
                _update_default_meeting_count(session, photo.group_id, -1)
                
                # Move photo to this meeting
                photo.meeting_id = meeting.id
                meeting.photo_count += 1
                meeting.updated_at = datetime.utcnow()
                
                session.add(photo)
                session.add(meeting)
                logger.info(f"Photo {photo.id} attached to existing meeting {meeting.id} (within time range)")
                return True
        
        # Step 2: Find closest meeting within GAP
        gap_interval = f"{meeting_gap_hours} hours"
        closest_meeting = session.exec(
            text(f"""
                SELECT * FROM meeting 
                WHERE group_id = :group_id 
                AND title != 'Default Meeting'
                AND :shot_at BETWEEN (start_time - INTERVAL '{gap_interval}') 
                                 AND (end_time + INTERVAL '{gap_interval}')
                ORDER BY ABS(EXTRACT(EPOCH FROM (:shot_at - start_time)))
                LIMIT 1
                FOR UPDATE
            """).bindparam(
                group_id=str(photo.group_id),
                shot_at=photo.shot_at
            )
        ).first()
        
        if closest_meeting:
            # Convert to Meeting object
            meeting = session.get(Meeting, closest_meeting.id)
            if meeting:
                # Update default meeting count (remove from default)
                _update_default_meeting_count(session, photo.group_id, -1)
                
                # Expand meeting time range if needed
                meeting.start_time = min(meeting.start_time, photo.shot_at)
                meeting.end_time = max(meeting.end_time, photo.shot_at)
                meeting.photo_count += 1
                meeting.updated_at = datetime.utcnow()
                
                # Move photo to this meeting
                photo.meeting_id = meeting.id
                
                session.add(photo)
                session.add(meeting)
                logger.info(f"Photo {photo.id} attached to closest meeting {meeting.id} (within GAP)")
                return True
        
        # Step 3: Create new meeting
        new_meeting = Meeting(
            group_id=photo.group_id,
            title=f"Meeting {photo.shot_at.strftime('%Y-%m-%d')}",
            description=f"Auto-created from photo taken at {photo.shot_at.strftime('%H:%M')}",
            start_time=photo.shot_at,
            end_time=photo.shot_at,
            meeting_date=photo.shot_at.date(),
            photo_count=1,
            participant_count=0,
        )
        session.add(new_meeting)
        session.flush()  # Get ID
        
        # Update default meeting count (remove from default)
        _update_default_meeting_count(session, photo.group_id, -1)
        
        # Move photo to new meeting
        photo.meeting_id = new_meeting.id
        session.add(photo)
        
        logger.info(f"Photo {photo.id} created new meeting {new_meeting.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to attach photo {photo.id} incrementally: {e}")
        return False


def _update_default_meeting_count(session: Session, group_id: str, delta: int) -> None:
    """Update Default Meeting photo count safely."""
    default_meeting = session.exec(
        select(Meeting).where(
            Meeting.group_id == group_id,
            Meeting.title == "Default Meeting"
        )
    ).first()
    
    if default_meeting:
        default_meeting.photo_count = max(0, default_meeting.photo_count + delta)
        default_meeting.updated_at = datetime.utcnow()
        session.add(default_meeting)


def _schedule_group_clustering(group_id: str) -> None:
    """
    Legacy function - now unused with incremental clustering.
    Kept for backward compatibility.
    """
    logger.info(f"Legacy clustering scheduler called for group {group_id} - using incremental clustering instead")


def cluster_group_if_ready(group_id: str, scheduled_time: int) -> bool:
    """
    Legacy function - now unused with incremental clustering.
    Kept for backward compatibility.
    """
    logger.info(f"Legacy delayed clustering called for group {group_id} - using incremental clustering instead")
    return True


def _cluster_group_photos_batch(group_id: str) -> bool:
    """
    Batch reclustering for the entire group - runs daily to merge and optimize meetings.
    This is the idempotent self-healing function mentioned in the design.
    
    Steps:
    1. Get all photos with timestamps in the group
    2. Re-cluster them using photo_core
    3. Merge nearby meetings that should be combined
    4. Update meeting time ranges and counts
    """
    try:
        with Session(engine) as session:
            logger.info(f"Starting batch reclustering for group {group_id}")
            
            # Get all photos with timestamps (excluding Default Meeting photos without timestamps)
            photos = session.exec(
                select(Photo).where(
                    Photo.group_id == group_id,
                    Photo.shot_at.is_not(None)
                )
            ).all()
            
            if len(photos) == 0:
                logger.info(f"No photos with timestamps in group {group_id}")
                return True
            
            # Convert to format expected by photo_core
            photo_dicts = []
            for photo in photos:
                photo_dicts.append({
                    "id": str(photo.id),
                    "DateTimeOriginal": photo.shot_at,
                    "group_id": str(photo.group_id),
                })
            
            # Use photo_core clustering
            clustered_photos = cluster_photos_into_meetings(photo_dicts)
            
            # Start transaction for batch update
            with session.begin():
                # Get existing non-default meetings
                existing_meetings = session.exec(
                    select(Meeting).where(
                        Meeting.group_id == group_id,
                        Meeting.title != "Default Meeting"
                    )
                ).all()
                
                # Create mapping of meeting dates to existing meetings
                meetings_by_date = {}
                for meeting in existing_meetings:
                    date_key = meeting.meeting_date
                    if date_key not in meetings_by_date:
                        meetings_by_date[date_key] = []
                    meetings_by_date[date_key].append(meeting)
                
                # Group clustered photos by meeting date
                clustered_by_date = {}
                for clustered_photo in clustered_photos:
                    meeting_date = clustered_photo.get("meeting_date")
                    if meeting_date:
                        if meeting_date not in clustered_by_date:
                            clustered_by_date[meeting_date] = []
                        clustered_by_date[meeting_date].append(clustered_photo)
                
                # Merge meetings for each date
                for meeting_date, clustered_photos_for_date in clustered_by_date.items():
                    existing_meetings_for_date = meetings_by_date.get(meeting_date, [])
                    
                    if len(existing_meetings_for_date) <= 1:
                        # No merge needed, just update existing meeting or create new one
                        if existing_meetings_for_date:
                            _update_meeting_from_photos(session, existing_meetings_for_date[0], clustered_photos_for_date)
                        else:
                            _create_meeting_from_photos(session, group_id, meeting_date, clustered_photos_for_date)
                    else:
                        # Merge multiple meetings for the same date
                        primary_meeting = existing_meetings_for_date[0]
                        
                        # Merge other meetings into the primary one
                        for meeting_to_merge in existing_meetings_for_date[1:]:
                            # Move photos from meeting_to_merge to primary_meeting
                            photos_to_move = session.exec(
                                select(Photo).where(Photo.meeting_id == meeting_to_merge.id)
                            ).all()
                            
                            for photo in photos_to_move:
                                photo.meeting_id = primary_meeting.id
                                session.add(photo)
                            
                            # Delete the merged meeting
                            session.delete(meeting_to_merge)
                            logger.info(f"Merged meeting {meeting_to_merge.id} into {primary_meeting.id}")
                        
                        # Update the primary meeting with all photos for this date
                        _update_meeting_from_photos(session, primary_meeting, clustered_photos_for_date)
                
                logger.info(f"Completed batch reclustering for group {group_id}")
                return True
                
    except Exception as e:
        logger.error(f"Batch reclustering failed for group {group_id}: {e}")
        return False


def _update_meeting_from_photos(session: Session, meeting: Meeting, clustered_photos: list) -> None:
    """Update meeting time range and count based on clustered photos."""
    if not clustered_photos:
        return
    
    # Calculate new time range
    times = [photo["DateTimeOriginal"] for photo in clustered_photos]
    meeting.start_time = min(times)
    meeting.end_time = max(times)
    meeting.photo_count = len(clustered_photos)
    meeting.updated_at = datetime.utcnow()
    
    session.add(meeting)
    logger.info(f"Updated meeting {meeting.id} with {len(clustered_photos)} photos")


def _create_meeting_from_photos(session: Session, group_id: str, meeting_date, clustered_photos: list) -> Meeting:
    """Create new meeting from clustered photos."""
    if not clustered_photos:
        return None
    
    times = [photo["DateTimeOriginal"] for photo in clustered_photos]
    start_time = min(times)
    end_time = max(times)
    
    new_meeting = Meeting(
        group_id=group_id,
        title=f"Meeting {meeting_date}",
        description=f"Auto-created meeting for {len(clustered_photos)} photos",
        start_time=start_time,
        end_time=end_time,
        meeting_date=meeting_date,
        photo_count=len(clustered_photos),
        participant_count=0,
    )
    session.add(new_meeting)
    session.flush()  # Get ID
    
    # Assign photos to this meeting
    for clustered_photo in clustered_photos:
        photo = session.get(Photo, clustered_photo["id"])
        if photo:
            photo.meeting_id = new_meeting.id
            session.add(photo)
    
    logger.info(f"Created new meeting {new_meeting.id} with {len(clustered_photos)} photos")
    return new_meeting


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
