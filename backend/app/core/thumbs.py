import logging
import subprocess
from pathlib import Path
from typing import Optional
from uuid import uuid4

from PIL import Image, ImageOps

from .config import settings

logger = logging.getLogger(__name__)


def create_thumbnail(src: Path, size: tuple[int, int] = None) -> Optional[Path]:
    """
    Create a thumbnail for an image or video file.

    Args:
        src: Source file path
        size: Thumbnail size (width, height). Defaults to settings.THUMBNAIL_SIZE

    Returns:
        Path to the created thumbnail or None if failed
    """
    if size is None:
        size = settings.THUMBNAIL_SIZE

    src_path = Path(src)
    if not src_path.exists():
        logger.error(f"Source file does not exist: {src_path}")
        return None

    # Generate thumbnail filename
    thumb_filename = f"thumb_{uuid4().hex[:8]}.jpg"
    thumb_path = src_path.parent / thumb_filename

    try:
        # Check if it's a video file
        if src_path.suffix.lower() in {".mov", ".mp4", ".avi", ".mkv"}:
            return _create_video_thumbnail(src_path, thumb_path, size)
        else:
            return _create_image_thumbnail(src_path, thumb_path, size)
    except Exception as e:
        logger.error(f"Failed to create thumbnail for {src_path}: {e}")
        return None


def _create_image_thumbnail(src: Path, dst: Path, size: tuple[int, int]) -> Path:
    """Create thumbnail for image files."""
    with Image.open(src) as img:
        # Handle EXIF orientation
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ("RGBA", "LA", "P"):
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(
                img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
            )
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Create thumbnail
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(dst, "JPEG", quality=settings.THUMBNAIL_QUALITY, optimize=True)

    logger.info(f"Created image thumbnail: {dst}")
    return dst


def _create_video_thumbnail(
    src: Path, dst: Path, size: tuple[int, int]
) -> Optional[Path]:
    """Create thumbnail for video files using ffmpeg."""
    try:
        # Use ffmpeg to extract frame at 1 second
        cmd = [
            "ffmpeg",
            "-i",
            str(src),
            "-ss",
            "00:00:01",  # Seek to 1 second
            "-vframes",
            "1",  # Extract 1 frame
            "-vf",
            f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease",
            "-y",  # Overwrite output file
            str(dst),
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30  # 30 second timeout
        )

        if result.returncode == 0 and dst.exists():
            logger.info(f"Created video thumbnail: {dst}")
            return dst
        else:
            logger.error(f"ffmpeg failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg timeout for {src}")
        return None
    except FileNotFoundError:
        logger.warning("ffmpeg not found, skipping video thumbnail")
        return None
    except Exception as e:
        logger.error(f"Error creating video thumbnail: {e}")
        return None
