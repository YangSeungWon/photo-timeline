import os
import shutil
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile, HTTPException, status

from .config import settings


def ensure_upload_dir() -> Path:
    """Ensure the upload directory exists."""
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase."""
    return Path(filename).suffix.lower()


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided"
        )

    extension = get_file_extension(file.filename)
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {extension} not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename while preserving the extension."""
    extension = get_file_extension(original_filename)
    unique_id = str(uuid4())
    return f"{unique_id}{extension}"


async def save_upload_file(file: UploadFile, group_id: str) -> tuple[str, str]:
    """
    Save uploaded file to disk.

    Returns:
        tuple: (filename, file_path)
    """
    validate_file(file)

    # Create group-specific directory
    upload_dir = ensure_upload_dir()
    group_dir = upload_dir / group_id
    group_dir.mkdir(exist_ok=True)

    # Generate unique filename
    filename = generate_unique_filename(file.filename)
    file_path = group_dir / filename

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB",
        )

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    return filename, str(file_path)
