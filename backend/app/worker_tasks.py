import logging
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select
from geoalchemy2.shape import to_shape

from .core.database import engine
from .core.thumbs import create_thumbnail
from .models.photo import Photo
from .models.meeting import Meeting
from .models.group import Group
from photo_core import extract_exif, cluster_photos_into_meetings

logger = logging.getLogger(__name__)


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

            # Step 2: Trigger meeting clustering
            if photo.meeting_id:
                meeting = session.get(Meeting, photo.meeting_id)
                if meeting:
                    _cluster_group_photos(session, meeting.group_id)

            # Step 3: Generate thumbnail
            _generate_thumbnail(session, photo, file_path)

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

        # Update photo with extracted metadata
        photo.exif_data = metadata

        # Set taken_at from EXIF datetime
        if "datetime" in metadata:
            photo.shot_at = metadata["datetime"]

        # Set GPS location if available
        if "gps_point" in metadata and metadata["gps_point"]:
            # metadata['gps_point'] should be a Point object or tuple from photo_core
            gps_point = metadata["gps_point"]
            if hasattr(gps_point, "x") and hasattr(gps_point, "y"):
                # Convert to PostGIS format
                photo.point_gps = f"POINT({gps_point.x} {gps_point.y})"
            elif isinstance(gps_point, (tuple, list)) and len(gps_point) >= 2:
                # Handle tuple/list format (longitude, latitude)
                photo.point_gps = f"POINT({gps_point[0]} {gps_point[1]})"

        session.add(photo)
        logger.info(f"Extracted EXIF data for photo {photo.id}")
        return True

    except Exception as e:
        logger.error(f"EXIF extraction failed for photo {photo.id}: {e}")
        return False


def _cluster_group_photos(session: Session, group_id: str) -> bool:
    """Trigger photo clustering for the entire group."""
    try:
        # Get all photos in the group that have taken_at timestamps
        stmt = (
            select(Photo)
            .join(Meeting)
            .where(Meeting.group_id == group_id)
            .where(Photo.shot_at.is_not(None))
        )
        photos = session.exec(stmt).all()

        if len(photos) < 2:
            logger.info(f"Not enough photos for clustering in group {group_id}")
            return True

        # Use photo_core clustering
        cluster_photos_into_meetings(session, group_id)
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
