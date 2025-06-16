import tempfile
import pytest
from pathlib import Path
from fastapi import UploadFile
from io import BytesIO

from backend.app.core.storage import (
    save_upload_file,
    validate_file,
    generate_unique_filename,
)


class TestStorage:
    """Test file storage functionality."""

    def test_generate_unique_filename(self):
        """Test unique filename generation."""
        filename1 = generate_unique_filename("test.jpg")
        filename2 = generate_unique_filename("test.jpg")

        # Should be different
        assert filename1 != filename2

        # Should preserve extension
        assert filename1.endswith(".jpg")
        assert filename2.endswith(".jpg")

    def test_validate_file_success(self):
        """Test file validation with valid file."""
        # Create a mock UploadFile
        file_content = b"fake image content"
        file = UploadFile(filename="test.jpg", file=BytesIO(file_content))

        # Should not raise exception
        validate_file(file)

    def test_validate_file_no_filename(self):
        """Test file validation with no filename."""
        from fastapi import HTTPException

        file = UploadFile(filename=None, file=BytesIO(b"content"))

        with pytest.raises(HTTPException) as exc_info:
            validate_file(file)
        assert "No filename provided" in exc_info.value.detail

    def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension."""
        from fastapi import HTTPException

        file = UploadFile(filename="test.txt", file=BytesIO(b"content"))

        with pytest.raises(HTTPException) as exc_info:
            validate_file(file)
        assert "not allowed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_save_upload_file(self):
        """Test saving upload file."""
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock settings
            import backend.app.core.storage as storage_module

            original_upload_dir = storage_module.settings.UPLOAD_DIR
            storage_module.settings.UPLOAD_DIR = temp_dir

            try:
                # Create mock file
                file_content = b"fake image content"
                file = UploadFile(filename="test.jpg", file=BytesIO(file_content))

                group_id = "test-group-123"

                # Save file
                filename, file_path = await save_upload_file(file, group_id)

                # Verify file was saved
                assert Path(file_path).exists()
                assert filename.endswith(".jpg")
                assert group_id in file_path

                # Verify content
                with open(file_path, "rb") as f:
                    saved_content = f.read()
                assert saved_content == file_content

            finally:
                # Restore original setting
                storage_module.settings.UPLOAD_DIR = original_upload_dir
