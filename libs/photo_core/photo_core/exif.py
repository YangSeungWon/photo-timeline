import json
import logging
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import piexif
    PIEXIF_AVAILABLE = True
except ImportError:
    piexif = None
    PIEXIF_AVAILABLE = False
    
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tiff", ".png"}
SUPPORTED_VIDEO_EXTENSIONS = {".mov", ".mp4"}
SUPPORTED_HEIC_EXTENSIONS = {".heic", ".heif"}

# Check exiftool availability once at module load
EXIFTOOL_AVAILABLE = shutil.which("exiftool") is not None

if not PIEXIF_AVAILABLE:
    logger.warning("piexif not installed – JPEG EXIF extraction disabled")
if not PIL_AVAILABLE:
    logger.warning("PIL/Pillow not installed – image processing disabled")
if not EXIFTOOL_AVAILABLE:
    logger.warning("exiftool not found in PATH – video/HEIC metadata disabled")


def _convert_gps_to_decimal(
    gps_coord: Optional[Tuple[Tuple[int, int], ...]],
    gps_ref: Optional[bytes],
) -> Optional[float]:
    """Converts GPS coordinates from EXIF format (degrees, minutes, seconds) to decimal degrees."""
    if not gps_coord or not gps_ref:
        return None

    try:
        degrees = gps_coord[0][0] / gps_coord[0][1]
        minutes = gps_coord[1][0] / gps_coord[1][1]
        seconds = gps_coord[2][0] / gps_coord[2][1]

        decimal = degrees + minutes / 60 + seconds / 3600

        if gps_ref.decode("utf-8").upper() in ["S", "W"]:
            decimal = -decimal

        return decimal
    except (IndexError, ZeroDivisionError, TypeError) as e:
        logger.warning(f"Could not parse GPS coordinate: {e}")
        return None


def _extract_video_metadata(file_path: Path) -> Dict[str, Any]:
    """Extracts metadata from video files using exiftool."""
    result = {"DateTimeOriginal": None, "GPSLat": None, "GPSLong": None}
    
    if not EXIFTOOL_AVAILABLE:
        logger.debug(f"exiftool not available, skipping video metadata for {file_path.name}")
        return result
        
    try:
        cmd = ["exiftool", "-j", "-n", str(file_path)]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if output.returncode == 0:
            data = json.loads(output.stdout)[0]
            # Try to find a date, checking common tags
            for date_field in ["DateTimeOriginal", "CreateDate", "MediaCreateDate"]:
                if date_field in data:
                    result["DateTimeOriginal"] = data[date_field]
                    break
            # GPS data (often in different tags for videos)
            if "GPSLatitude" in data and "GPSLongitude" in data:
                result["GPSLat"] = data.get("GPSLatitude")
                result["GPSLong"] = data.get("GPSLongitude")

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        json.JSONDecodeError,
    ) as e:
        logger.warning(
            f"exiftool processing failed for {file_path.name}: {e}. "
            "Ensure exiftool is installed and in your PATH."
        )

    return result


def _extract_heic_metadata(file_path: Path) -> Dict[str, Any]:
    """Extracts metadata from HEIC files using exiftool."""
    result = {"DateTimeOriginal": None, "GPSLat": None, "GPSLong": None}
    
    if not EXIFTOOL_AVAILABLE:
        logger.debug(f"exiftool not available, skipping HEIC metadata for {file_path.name}")
        return result
        
    try:
        cmd = ["exiftool", "-j", "-n", str(file_path)]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if output.returncode == 0:
            data = json.loads(output.stdout)[0]
            # Try to find a date, checking common tags
            for date_field in ["DateTimeOriginal", "CreateDate", "DateCreated"]:
                if date_field in data:
                    result["DateTimeOriginal"] = data[date_field]
                    break
            # GPS data
            if "GPSLatitude" in data and "GPSLongitude" in data:
                result["GPSLat"] = data.get("GPSLatitude")
                result["GPSLong"] = data.get("GPSLongitude")

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        json.JSONDecodeError,
    ) as e:
        logger.warning(
            f"exiftool processing failed for HEIC {file_path.name}: {e}. "
            "Ensure exiftool is installed and in your PATH."
        )

    return result


def extract_exif(file_path: Path) -> Dict[str, Any]:
    """
    Extracts key EXIF data from a single image or video file.

    Args:
        file_path: Path to the file.

    Returns:
        A dictionary containing metadata.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    result: Dict[str, Any] = {
        "FileName": file_path.name,
        "FilePath": str(file_path),
        "DateTimeOriginal": None,
        "GPSLat": None,
        "GPSLong": None,
    }

    try:
        if suffix in SUPPORTED_IMAGE_EXTENSIONS:
            if not PIEXIF_AVAILABLE:
                logger.debug(f"piexif not available, skipping EXIF for {file_path.name}")
                return result
            exif_dict = piexif.load(str(file_path))

            # Date/Time
            if piexif.ExifIFD.DateTimeOriginal in exif_dict.get("Exif", {}):
                date_bytes = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal]
                result["DateTimeOriginal"] = date_bytes.decode("utf-8")

            # GPS
            gps_info = exif_dict.get("GPS", {})
            if gps_info:
                result["GPSLat"] = _convert_gps_to_decimal(
                    gps_info.get(piexif.GPSIFD.GPSLatitude),
                    gps_info.get(piexif.GPSIFD.GPSLatitudeRef),
                )
                result["GPSLong"] = _convert_gps_to_decimal(
                    gps_info.get(piexif.GPSIFD.GPSLongitude),
                    gps_info.get(piexif.GPSIFD.GPSLongitudeRef),
                )

        elif suffix in SUPPORTED_VIDEO_EXTENSIONS:
            result.update(_extract_video_metadata(file_path))

        elif suffix in SUPPORTED_HEIC_EXTENSIONS:
            result.update(_extract_heic_metadata(file_path))

        else:
            logger.debug(f"Unsupported file type for EXIF extraction: {file_path.name}")

    except Exception as e:
        logger.error(f"Failed to extract EXIF for {file_path.name}: {e}")

    # Final conversion to datetime object
    if isinstance(result["DateTimeOriginal"], str):
        try:
            # Common EXIF format: 'YYYY:MM:DD HH:MM:SS'
            result["DateTimeOriginal"] = datetime.strptime(
                result["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S"
            )
        except ValueError:
            logger.warning(f"Could not parse date string: {result['DateTimeOriginal']}")
            result["DateTimeOriginal"] = None

    return result


def patch_exif(file_path: Path, shot_at: datetime, gps: Tuple[float, float]):
    """
    Writes new Date/Time and GPS data to a JPEG file's EXIF.

    Args:
        file_path: Path to the JPEG file.
        shot_at: The new timestamp to write.
        gps: A tuple of (latitude, longitude) to write.
    """
    # This is a placeholder for the EXIF patching logic (F-7)
    # It will involve piexif.dump() and piexif.insert()
    logger.info(f"Patching {file_path.name} with timestamp={shot_at}, gps={gps}")
    # Example using piexif:
    # exif_dict = piexif.load(str(file_path))
    # exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = shot_at.strftime("%Y:%m:%d %H:%M:%S").encode('utf-8')
    # ... GPS conversion to rational format needed here ...
    # exif_bytes = piexif.dump(exif_dict)
    # piexif.insert(exif_bytes, str(file_path))
    pass


def suggest_timestamps(
    photos: List[Dict[str, Any]], target_filename: str
) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
    """
    Suggests timestamps for a photo based on adjacent photos with timestamps.

    Args:
        photos: List of photo metadata dictionaries with 'FileName' and 'DateTimeOriginal'
        target_filename: The filename of the photo needing a timestamp suggestion

    Returns:
        A tuple of (prev_plus_1s, middle, next_minus_1s) datetime suggestions.
        Any of these can be None if the adjacent photo doesn't exist.
    """
    # Filter photos that have timestamps and sort by filename
    dated_photos = [
        p for p in photos if p.get("DateTimeOriginal") and p.get("FileName")
    ]
    dated_photos.sort(key=lambda p: p["FileName"])

    # Find photos before and after the target
    prev_photo = None
    next_photo = None

    for photo in dated_photos:
        if photo["FileName"] < target_filename:
            prev_photo = photo
        elif photo["FileName"] > target_filename:
            next_photo = photo
            break

    # Generate suggestions
    prev_plus_1s = None
    middle = None
    next_minus_1s = None

    if prev_photo:
        prev_dt = prev_photo["DateTimeOriginal"]
        if isinstance(prev_dt, str):
            try:
                prev_dt = datetime.strptime(prev_dt, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                prev_dt = None

        if prev_dt:
            prev_plus_1s = prev_dt + timedelta(seconds=1)

    if next_photo:
        next_dt = next_photo["DateTimeOriginal"]
        if isinstance(next_dt, str):
            try:
                next_dt = datetime.strptime(next_dt, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                next_dt = None

        if next_dt:
            next_minus_1s = next_dt - timedelta(seconds=1)

    # Calculate middle time if both prev and next exist
    if prev_plus_1s and next_minus_1s:
        # Use the actual prev and next times (not the +1s/-1s versions)
        prev_dt = prev_plus_1s - timedelta(seconds=1)
        next_dt = next_minus_1s + timedelta(seconds=1)
        time_diff = next_dt - prev_dt
        middle = prev_dt + time_diff / 2

    return prev_plus_1s, middle, next_minus_1s
