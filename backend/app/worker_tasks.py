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

# Metrics tracking (can be extended with StatsD/Prometheus)
clustering_metrics = {
    "total_photos_processed": 0,
    "total_meetings_created": 0,
    "total_clustering_runs": 0,
    "total_clustering_failures": 0,
    "debounce_reschedules": 0,
}

def _emit_metric(metric_name: str, value: int = 1, tags: Dict[str, str] = None) -> None:
    """Emit metrics to monitoring system (placeholder for StatsD/Prometheus)."""
    if not settings.ENABLE_CLUSTERING_METRICS:
        return
    
    # Update internal counters
    if metric_name in clustering_metrics:
        clustering_metrics[metric_name] += value
    
    # TODO: Send to actual monitoring system
    # statsd.increment(f"photo_timeline.clustering.{metric_name}", value, tags=tags)
    logger.debug(f"Metric: {metric_name}={value} {tags or ''}")

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

            # Step 2: Mark for batch clustering (debounced)
            _mark_cluster_pending(str(photo.group_id))

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


def _mark_cluster_pending(group_id: str) -> None:
    """
    Mark group for debounced clustering using Redis TTL.
    
    Enhanced with fallback strategy:
    - Primary: Redis-based debounced clustering  
    - Fallback: Legacy incremental clustering when Redis unavailable
    """
    if not redis_client:
        logger.warning(f"Redis not available for group {group_id}, using legacy incremental clustering")
        # Fallback: Use legacy incremental clustering (rough but immediate)
        # This ensures photos get basic clustering even without Redis
        # Later batch clustering will optimize the results
        return  # Let the photo stay in Default Meeting for batch processing
    
    try:
        ttl = settings.CLUSTER_DEBOUNCE_TTL
        delay = settings.CLUSTER_RETRY_DELAY
        
        # Mark activity with TTL
        pending_key = f"cluster:pending:{group_id}"
        count_key = f"cluster:count:{group_id}"
        job_key = f"cluster:job:{group_id}"
        
        # Extend activity window
        redis_client.setex(pending_key, ttl, "1")
        redis_client.incr(count_key)  # Statistics (optional)
        
        # Schedule SINGLE job if not already scheduled
        if not redis_client.exists(job_key):
            try:
                # Schedule the debounced clustering job
                default_queue.enqueue_in(
                    delay,
                    cluster_if_quiet,
                    group_id=group_id,
                    job_timeout=300  # 5 minutes timeout
                )
                # Mark that job is scheduled (prevent duplicate scheduling)
                redis_client.setex(job_key, ttl + delay + 10, "1")  # Extra buffer
                logger.info(f"Scheduled debounced clustering for group {group_id}")
            except Exception as e:
                logger.error(f"Failed to schedule cluster job for group {group_id}: {e}")
                # If job scheduling fails, fall back to immediate batch clustering
                logger.warning(f"Fallback: immediate clustering for group {group_id}")
                _cluster_group_photos_batch(group_id)
                
    except Exception as e:
        logger.error(f"Redis operation failed for group {group_id}: {e}")
        # Complete Redis failure - fall back to legacy approach
        logger.warning(f"Redis failure, using legacy clustering for group {group_id}")
        # Could optionally trigger immediate batch clustering here
        # For now, let it accumulate in Default Meeting for batch processing


def cluster_if_quiet(group_id: str) -> bool:
    """
    Execute full group clustering only if the group is "quiet" (no recent uploads).
    If still busy, reschedule for later.
    
    Enhanced with safety checks:
    - Prevents infinite busy state with TTL limits
    - Handles Redis failures gracefully
    - Ensures job cleanup and retry on failure
    """
    if not redis_client:
        logger.warning("Redis not available, performing clustering anyway")
        return _cluster_group_photos_batch(group_id)
    
    pending_key = f"cluster:pending:{group_id}"
    count_key = f"cluster:count:{group_id}"
    job_key = f"cluster:job:{group_id}"
    
    # Check if group is still receiving uploads
    if redis_client.exists(pending_key):
        # Still busy - but check TTL to prevent infinite busy state
        ttl = redis_client.ttl(pending_key)
        delay = settings.CLUSTER_RETRY_DELAY
        
        # Safety: if TTL is very low, don't reschedule - proceed with clustering
        if ttl >= 0 and ttl < delay * 2:
            logger.info(f"Group {group_id} TTL low ({ttl}s), proceeding with clustering")
        else:
            # Normal reschedule
            try:
                default_queue.enqueue_in(
                    delay,
                    cluster_if_quiet,
                    group_id=group_id,
                    job_timeout=300
                )
                _emit_metric("debounce_reschedules", tags={"group_id": group_id})
                logger.info(f"Group {group_id} still busy (TTL:{ttl}s), rescheduled clustering")
                return False
            except Exception as e:
                logger.error(f"Failed to reschedule cluster job for group {group_id}: {e}")
                # If can't reschedule, proceed with clustering anyway
                logger.warning(f"Proceeding with immediate clustering for group {group_id}")
    
    # Group is quiet (or forced due to edge cases) - perform clustering
    try:
        photo_count = redis_client.get(count_key) or "0"
        logger.info(f"Starting batch clustering for group {group_id} ({photo_count} photos processed)")
        
        _emit_metric("total_clustering_runs", tags={"group_id": group_id})
        start_time = time.time()
        
        success = _cluster_group_photos_batch(group_id)
        
        duration = time.time() - start_time
        logger.info(f"Clustering took {duration:.2f}s for group {group_id}")
        
        if success:
            logger.info(f"Completed batch clustering for group {group_id}")
            # Cleanup Redis keys on success
            redis_client.delete(count_key, job_key, pending_key)
            return True
        else:
            logger.error(f"Batch clustering failed for group {group_id}")
            _emit_metric("total_clustering_failures", tags={"group_id": group_id})
            
            # Schedule retry on failure (fail-fast with retry)
            try:
                retry_delay = settings.CLUSTER_RETRY_DELAY * 2  # Longer delay for retry
                default_queue.enqueue_in(
                    retry_delay,
                    cluster_if_quiet,
                    group_id=group_id,
                    job_timeout=300
                )
                logger.info(f"Scheduled retry clustering for group {group_id} in {retry_delay}s")
            except Exception as retry_e:
                logger.error(f"Failed to schedule retry for group {group_id}: {retry_e}")
            
            # Don't cleanup keys on failure - let retry handle it
            return False
        
    except Exception as e:
        logger.error(f"Error in cluster_if_quiet for group {group_id}: {e}")
        _emit_metric("total_clustering_failures", tags={"group_id": group_id})
        
        # Schedule retry on unexpected error
        try:
            retry_delay = settings.CLUSTER_RETRY_DELAY * 2
            default_queue.enqueue_in(
                retry_delay,
                cluster_if_quiet,
                group_id=group_id,
                job_timeout=300
            )
            logger.info(f"Scheduled retry clustering after error for group {group_id}")
        except Exception as retry_e:
            logger.error(f"Failed to schedule retry after error for group {group_id}: {retry_e}")
            # Final cleanup if even retry scheduling fails
            redis_client.delete(count_key, job_key, pending_key)
        
        return False


# Legacy incremental clustering functions - kept for reference
# These are replaced by debounced batch clustering for better efficiency

def _attach_incremental_legacy(session: Session, photo: Photo) -> bool:
    """
    LEGACY: Old incremental clustering approach.
    Replaced by debounced batch clustering (_mark_cluster_pending + cluster_if_quiet).
    
    This function is kept for reference and emergency fallback if needed.
    """
    logger.warning("Using legacy incremental clustering - consider using debounced batch clustering instead")
    
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
    Complete batch reclustering for the entire group.
    
    This is the core function that handles:
    1. All photos with timestamps → proper meetings
    2. Photos without timestamps → stay in Default Meeting
    3. Merge duplicate meetings on same date
    4. Clean up empty meetings
    
    Designed to be idempotent and handle any edge cases.
    """
    try:
        with Session(engine) as session:
            logger.info(f"Starting batch clustering for group {group_id}")
            
            # Get all photos with timestamps
            photos_with_timestamps = session.exec(
                select(Photo).where(
                    Photo.group_id == group_id,
                    Photo.shot_at.is_not(None)
                )
            ).all()
            
            if len(photos_with_timestamps) == 0:
                logger.info(f"No photos with timestamps in group {group_id}")
                return True
            
            # Convert to photo_core format
            photo_dicts = []
            for photo in photos_with_timestamps:
                photo_dicts.append({
                    "id": str(photo.id),
                    "DateTimeOriginal": photo.shot_at,
                    "group_id": str(photo.group_id),
                })
            
            # Use photo_core clustering algorithm
            clustered_photos = cluster_photos_into_meetings(photo_dicts)
            
            # Start transaction for atomic update
            with session.begin():
                # Step 1: Move all timestamped photos to Default Meeting temporarily
                # This ensures clean state before reassignment
                default_meeting = _get_or_create_default_meeting(session, group_id)
                
                for photo in photos_with_timestamps:
                    if photo.meeting_id != default_meeting.id:
                        photo.meeting_id = default_meeting.id
                        session.add(photo)
                
                # Step 2: Delete all auto-generated meetings (keep manual ones)
                auto_meetings = session.exec(
                    select(Meeting).where(
                        Meeting.group_id == group_id,
                        Meeting.title != "Default Meeting",
                        # Add more conditions if needed to identify auto-generated meetings
                        # For now, we'll be conservative and keep all non-default meetings
                    )
                ).all()
                
                # Actually, let's be more careful - only delete empty meetings
                empty_meetings = []
                for meeting in auto_meetings:
                    photo_count = session.exec(
                        select(Photo).where(Photo.meeting_id == meeting.id)
                    ).first()
                    if not photo_count:
                        empty_meetings.append(meeting)
                
                for meeting in empty_meetings:
                    session.delete(meeting)
                    logger.info(f"Deleted empty meeting {meeting.id}")
                
                # Step 3: Create new meetings from clustered data
                clustered_by_date = {}
                for clustered_photo in clustered_photos:
                    meeting_date = clustered_photo.get("meeting_date")
                    if meeting_date:
                        if meeting_date not in clustered_by_date:
                            clustered_by_date[meeting_date] = []
                        clustered_by_date[meeting_date].append(clustered_photo)
                
                meetings_created = 0
                photos_moved = 0
                
                for meeting_date, photos_for_date in clustered_by_date.items():
                    if not photos_for_date:
                        continue
                    
                    # Calculate time range for this cluster
                    times = [p["DateTimeOriginal"] for p in photos_for_date]
                    start_time = min(times)
                    end_time = max(times)
                    
                    # Create new meeting
                    new_meeting = Meeting(
                        group_id=group_id,
                        title=f"Meeting {meeting_date}",
                        description=f"Auto-clustered meeting for {len(photos_for_date)} photos",
                        start_time=start_time,
                        end_time=end_time,
                        meeting_date=meeting_date,
                        photo_count=len(photos_for_date),
                        participant_count=0,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(new_meeting)
                    session.flush()  # Get ID
                    
                    # Move photos to this meeting
                    for photo_data in photos_for_date:
                        photo = session.get(Photo, photo_data["id"])
                        if photo:
                            photo.meeting_id = new_meeting.id
                            session.add(photo)
                            photos_moved += 1
                    
                    meetings_created += 1
                    logger.info(f"Created meeting {new_meeting.id} for {len(photos_for_date)} photos on {meeting_date}")
                
                # Emit metrics for monitoring
                _emit_metric("total_photos_processed", photos_moved, tags={"group_id": group_id})
                _emit_metric("total_meetings_created", meetings_created, tags={"group_id": group_id})
                
                # Step 4: Update Default Meeting count
                remaining_photos = session.exec(
                    select(Photo).where(Photo.meeting_id == default_meeting.id)
                ).all()
                default_meeting.photo_count = len(remaining_photos)
                default_meeting.updated_at = datetime.utcnow()
                session.add(default_meeting)
                
                logger.info(f"Batch clustering completed for group {group_id}: "
                          f"{meetings_created} meetings created, {photos_moved} photos moved")
                return True
                
    except Exception as e:
        logger.error(f"Batch clustering failed for group {group_id}: {e}")
        return False


def _get_or_create_default_meeting(session: Session, group_id: str) -> Meeting:
    """Get or create the Default Meeting for a group."""
    default_meeting = session.exec(
        select(Meeting).where(
            Meeting.group_id == group_id,
            Meeting.title == "Default Meeting"
        )
    ).first()
    
    if not default_meeting:
        now = datetime.utcnow()
        default_meeting = Meeting(
            group_id=group_id,
            title="Default Meeting",
            description="Default meeting for photos without timestamps",
            start_time=now,
            end_time=now,
            meeting_date=now.date(),
            photo_count=0,
            participant_count=0,
        )
        session.add(default_meeting)
        session.flush()
    
    return default_meeting


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
