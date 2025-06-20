import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from sqlmodel import Session, select
from sqlalchemy import text
from geoalchemy2.shape import to_shape
from geoalchemy2 import WKTElement
import redis
import time

from .core.database import engine
from .core.thumbs import create_thumbnail
from .core.queues import default_queue, get_cluster_queue
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
    
    if tags is None:
        tags = {}
    
    # Update internal counters
    if metric_name in clustering_metrics:
        clustering_metrics[metric_name] += value
    
    # TODO: Send to actual monitoring system
    # statsd.increment(f"photo_timeline.clustering.{metric_name}", value, tags=tags)
    logger.debug(f"Metric: {metric_name}={value} {tags}")

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
        logger.info(f"Starting EXIF extraction for photo {photo.id}, file: {file_path}")
        metadata = extract_exif(file_path)
        
        logger.info(f"Raw EXIF metadata for photo {photo.id}: {metadata}")

        # Serialize EXIF data for JSON storage
        serialized_metadata = serialize_exif_data(metadata)
        photo.exif_data = serialized_metadata

        # Set taken_at from EXIF datetime
        if "DateTimeOriginal" in metadata:
            photo.shot_at = metadata["DateTimeOriginal"]
            logger.info(f"Set shot_at for photo {photo.id}: {photo.shot_at}")

        # Set GPS location if available
        if "GPSLat" in metadata and "GPSLong" in metadata:
            lat = metadata["GPSLat"]
            lon = metadata["GPSLong"]
            logger.info(f"Found GPS coordinates for photo {photo.id}: lat={lat}, lon={lon}")
            
            if lat is not None and lon is not None:
                # Store individual GPS coordinates
                photo.gps_latitude = float(lat)
                photo.gps_longitude = float(lon)
                
                # PostGIS Geometry (srid = 4326) 로 저장해야 to_shape() 가 동작
                photo.point_gps = WKTElement(f"POINT({lon} {lat})", srid=4326)
                logger.info(f"Set GPS fields for photo {photo.id}: lat={lat}, lon={lon}, point_gps=POINT({lon} {lat}) with SRID 4326")
            else:
                logger.warning(f"GPS coordinates are None for photo {photo.id}")
        else:
            logger.info(f"No GPS coordinates found in EXIF for photo {photo.id}")

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


def _require_redis() -> bool:
    """Check if Redis is available and responsive."""
    if not redis_client:
        logger.error("❌ REDIS: redis_client is None (init 실패)")
        return False
    try:
        redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"❌ REDIS: ping 실패 – {e}")
        return False


def _mark_cluster_pending(group_id: str) -> None:
    """
    Mark group for debounced clustering using Redis TTL.
    
    Enhanced with fallback strategy and robust Redis key management:
    - Primary: Redis-based debounced clustering  
    - Fallback: Accumulate in Default Meeting for batch processing
    - Safe TTL management to prevent infinite busy states
    """
    logger.info(f"🔍 DEBUG: _mark_cluster_pending called for group {group_id}")
    
    # Enhanced Redis availability check
    if not _require_redis():
        logger.warning(f"❌ REDIS: Redis unavailable for group {group_id}, falling back to Default Meeting")
        return
    
    logger.info(f"✅ REDIS: Redis client available, proceeding with clustering setup for group {group_id}")
    
    try:
        # Safe TTL values with minimum guarantees
        ttl = max(settings.CLUSTER_DEBOUNCE_TTL, 5)  # Minimum 5 seconds
        delay = max(settings.CLUSTER_RETRY_DELAY, 3)  # Minimum 3 seconds
        
        if settings.CLUSTER_DEBOUNCE_TTL < 5:
            logger.warning(f"⚠️ REDIS: CLUSTER_DEBOUNCE_TTL ({settings.CLUSTER_DEBOUNCE_TTL}) too low, using {ttl}s")
        if settings.CLUSTER_RETRY_DELAY < 3:
            logger.warning(f"⚠️ REDIS: CLUSTER_RETRY_DELAY ({settings.CLUSTER_RETRY_DELAY}) too low, using {delay}s")
        
        # Mark activity with TTL
        pending_key = f"cluster:pending:{group_id}"
        count_key = f"cluster:count:{group_id}"
        job_key = f"cluster:job:{group_id}"
        
        logger.info(f"🔑 REDIS: Setting up keys - pending: {pending_key}, job: {job_key}, count: {count_key}")
        logger.info(f"⏰ REDIS: TTL={ttl}s, delay={delay}s")
        
        # Set pending key with TTL
        logger.info(f"📝 REDIS: Setting pending key '{pending_key}' with TTL {ttl}s")
        redis_result = redis_client.setex(pending_key, ttl, "1")
        logger.info(f"✅ REDIS: setex('{pending_key}', {ttl}, '1') -> {redis_result}")
        
        # Increment count
        logger.info(f"📈 REDIS: Incrementing count key '{count_key}'")
        count_result = redis_client.incr(count_key)
        logger.info(f"✅ REDIS: incr('{count_key}') -> {count_result}")
        
        # Check if job key exists
        logger.info(f"🔍 REDIS: Checking if job key '{job_key}' exists")
        job_exists = redis_client.exists(job_key)
        logger.info(f"✅ REDIS: exists('{job_key}') -> {job_exists}")
        
        # Schedule SINGLE job if not already scheduled
        if not job_exists:
            try:
                logger.info(f"🎯 REDIS: Job key doesn't exist, scheduling clustering job for group {group_id}")
                logger.info(f"📅 REDIS: Calling enqueue_in(delay={delay}, func=cluster_if_quiet, group_id={group_id})")
                
                # Schedule the debounced clustering job on dedicated cluster queue
                cluster_queue = get_cluster_queue()
                job = cluster_queue.enqueue_in(
                    timedelta(seconds=delay),  # Use timedelta, not int
                    cluster_if_quiet,
                    group_id=group_id,
                    job_timeout=300  # 5 minutes timeout
                )
                logger.info(f"✅ REDIS: enqueue_in() successful, job_id={job.id}")
                
                # Mark that job is scheduled with longer TTL to prevent duplicate scheduling
                job_ttl = ttl + delay + 30
                logger.info(f"📝 REDIS: Setting job key '{job_key}' with TTL {job_ttl}s")
                job_key_result = redis_client.setex(job_key, job_ttl, "1")
                logger.info(f"✅ REDIS: setex('{job_key}', {job_ttl}, '1') -> {job_key_result}")
                
                logger.info(f"🎉 REDIS: Successfully scheduled debounced clustering for group {group_id} in {delay}s")
            except Exception as e:
                logger.error(f"❌ REDIS: Failed to schedule cluster job for group {group_id}: {e}")
                logger.error(f"❌ REDIS: Exception type: {type(e).__name__}")
                logger.error(f"❌ REDIS: Exception details: {str(e)}")
                
                # Clean up job key on failure
                try:
                    logger.info(f"🧹 REDIS: Cleaning up job key '{job_key}' due to scheduling failure")
                    delete_result = redis_client.delete(job_key)
                    logger.info(f"✅ REDIS: delete('{job_key}') -> {delete_result}")
                except Exception as cleanup_e:
                    logger.error(f"❌ REDIS: Failed to cleanup job key: {cleanup_e}")
                
                logger.warning(f"Will rely on periodic batch clustering for group {group_id}")
        else:
            logger.info(f"⏭️ REDIS: Job already scheduled for group {group_id}, skipping job creation")
                
    except Exception as e:
        logger.error(f"❌ REDIS: Redis operation failed for group {group_id}: {e}")
        logger.error(f"❌ REDIS: Exception type: {type(e).__name__}")
        logger.error(f"❌ REDIS: Exception details: {str(e)}")
        # Complete Redis failure - fall back to batch processing
        logger.warning(f"Redis failure, will rely on batch clustering for group {group_id}")


def cluster_if_quiet(group_id: str) -> bool:
    """
    Execute full group clustering only if the group is "quiet" (no recent uploads).
    If still busy, reschedule for later.
    
    Enhanced with safety checks:
    - Prevents infinite busy state with TTL limits
    - Handles Redis failures gracefully  
    - Ensures job cleanup and retry on failure
    - Automatic TTL extension for edge cases
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
        
        # Safety: if TTL is very low (< 2 seconds), slightly extend it but proceed
        if ttl >= 0 and ttl < 2:
            logger.info(f"Group {group_id} TTL very low ({ttl}s), extending slightly but proceeding")
            redis_client.expire(pending_key, settings.CLUSTER_DEBOUNCE_TTL)
        # If TTL is reasonable but low, proceed with clustering to avoid infinite wait
        elif ttl >= 0 and ttl < delay:
            logger.info(f"Group {group_id} TTL low ({ttl}s), proceeding with clustering")
        else:
            # Normal reschedule - still busy with healthy TTL
            try:
                cluster_queue = get_cluster_queue()
                cluster_queue.enqueue_in(
                    timedelta(seconds=delay),  # Use timedelta, not int
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
                logger.warning(f"Reschedule failed, proceeding with immediate clustering for group {group_id}")
    
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
            
            # Schedule retry on failure with exponential backoff
            try:
                retry_delay = settings.CLUSTER_RETRY_DELAY * 2  # Longer delay for retry
                cluster_queue = get_cluster_queue()
                cluster_queue.enqueue_in(
                    timedelta(seconds=retry_delay),  # Use timedelta, not int
                    cluster_if_quiet,
                    group_id=group_id,
                    job_timeout=300
                )
                logger.info(f"Scheduled retry clustering for group {group_id} in {retry_delay}s")
            except Exception as retry_e:
                logger.error(f"Failed to schedule retry for group {group_id}: {retry_e}")
                # Clean up keys if can't retry
                redis_client.delete(count_key, job_key, pending_key)
            
            return False
        
    except Exception as e:
        logger.error(f"Error in cluster_if_quiet for group {group_id}: {e}")
        _emit_metric("total_clustering_failures", tags={"group_id": group_id})
        
        # Schedule retry on unexpected error
        try:
            retry_delay = settings.CLUSTER_RETRY_DELAY * 2  # int calculation
            cluster_queue = get_cluster_queue()
            cluster_queue.enqueue_in(
                timedelta(seconds=retry_delay),  # Use timedelta, not int
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
    
    This function creates its own database session to avoid transaction conflicts
    with the calling process_photo() session.
    
    Steps:
    1. All photos with timestamps → proper meetings
    2. Photos without timestamps → stay in Default Meeting
    3. Merge duplicate meetings on same date
    4. Clean up empty meetings
    
    Designed to be idempotent and handle any edge cases.
    """
    try:
        # Create separate session to avoid transaction conflicts
        from app.core.database import engine
        session = Session(engine, autocommit=False, autoflush=False)
        
        try:
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
            from sqlalchemy import func
            empty_meetings = []
            for meeting in auto_meetings:
                photo_count = session.exec(
                    select(func.count(Photo.id)).where(Photo.meeting_id == meeting.id)
                ).first() or 0
                if photo_count == 0:
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

                # ── ① 이미 같은 date/title 이 존재하면 가져옴 ───────────────────
                existing = session.exec(
                    select(Meeting).where(
                        Meeting.group_id == group_id,
                        Meeting.title == f"Meeting {meeting_date}"
                    ).limit(1)
                ).first()

                times = [p["DateTimeOriginal"] for p in photos_for_date]
                start_time, end_time = min(times), max(times)

                if existing:          # ▷ UPDATE / MERGE
                    existing.start_time = min(existing.start_time, start_time)
                    existing.end_time   = max(existing.end_time,   end_time)
                    existing.photo_count += len(photos_for_date)
                    existing.updated_at  = datetime.utcnow()
                    target_meeting = existing
                    session.add(existing)
                    logger.info(f"Updated existing meeting {existing.id} with {len(photos_for_date)} more photos on {meeting_date}")
                else:                 # ▷ 새로 INSERT
                    target_meeting = Meeting(
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
                    session.add(target_meeting)
                    session.flush()  # Get ID
                    meetings_created += 1
                    logger.info(f"Created new meeting {target_meeting.id} for {len(photos_for_date)} photos on {meeting_date}")
                
                # Move photos to this meeting
                for photo_data in photos_for_date:
                    photo = session.get(Photo, photo_data["id"])
                    if photo:
                        photo.meeting_id = target_meeting.id
                        session.add(photo)
                        photos_moved += 1
            
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
            
            # Commit all changes
            session.commit()
            
            logger.info(f"Batch clustering completed for group {group_id}: "
                      f"{meetings_created} meetings created, {photos_moved} photos moved")
            return True
        
        except Exception as inner_e:
            logger.error(f"Batch clustering failed for group {group_id}: {inner_e}")
            session.rollback()
            return False
        finally:
            session.close()
                
    except Exception as e:
        logger.error(f"Failed to create session for batch clustering group {group_id}: {e}")
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


def get_clustering_metrics() -> Dict[str, Any]:
    """
    Get current clustering system metrics and health status.
    Useful for monitoring and debugging.
    """
    try:
        metrics = {
            "internal_counters": clustering_metrics.copy(),
            "redis_connected": redis_client is not None,
            "settings": {
                "CLUSTER_DEBOUNCE_TTL": settings.CLUSTER_DEBOUNCE_TTL,
                "CLUSTER_RETRY_DELAY": settings.CLUSTER_RETRY_DELAY,
                "CLUSTER_MAX_RETRIES": settings.CLUSTER_MAX_RETRIES,
                "MEETING_GAP_HOURS": settings.MEETING_GAP_HOURS,
            }
        }
        
        if redis_client:
            # Get active Redis keys for all groups
            pending_keys = redis_client.keys("cluster:pending:*")
            job_keys = redis_client.keys("cluster:job:*") 
            count_keys = redis_client.keys("cluster:count:*")
            
            metrics["redis_status"] = {
                "pending_groups": len(pending_keys),
                "scheduled_jobs": len(job_keys),
                "active_counts": len(count_keys),
                "sample_keys": {
                    "pending": pending_keys[:3],  # Show first 3
                    "jobs": job_keys[:3],
                    "counts": count_keys[:3],
                }
            }
        else:
            metrics["redis_status"] = "disconnected"
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get clustering metrics: {e}")
        return {"error": str(e)}


def cleanup_stale_redis_keys(max_age_seconds: int = 3600) -> int:
    """
    Clean up Redis keys that might be left over from crashed workers.
    Returns number of keys cleaned up.
    """
    if not redis_client:
        return 0
    
    cleaned = 0
    try:
        # Find job keys without corresponding pending keys (orphaned jobs)
        job_keys = redis_client.keys("cluster:job:*")
        for job_key in job_keys:
            group_id = job_key.split(":")[-1]
            pending_key = f"cluster:pending:{group_id}"
            
            # If job key exists but no pending key, it might be stale
            if not redis_client.exists(pending_key):
                ttl = redis_client.ttl(job_key)
                # If TTL is very high, it might be stale from a crashed worker
                if ttl > max_age_seconds:
                    redis_client.delete(job_key)
                    cleaned += 1
                    logger.info(f"Cleaned up stale job key: {job_key}")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"Failed to cleanup stale Redis keys: {e}")
        return 0
