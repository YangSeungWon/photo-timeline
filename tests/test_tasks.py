import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime

from sqlmodel import Session, create_engine, SQLModel
from fakeredis import FakeRedis
from PIL import Image

from backend.app.core.database import get_db
from backend.app.models.photo import Photo
from backend.app.models.meeting import Meeting
from backend.app.models.group import Group
from backend.app.models.user import User
from backend.app.worker_tasks import (
    process_photo,
    _extract_exif_data,
    _generate_thumbnail,
)
from backend.app.core.thumbs import create_thumbnail


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_image(temp_dir):
    """Create a test JPEG image with EXIF data."""
    image_path = temp_dir / "test_image.jpg"

    # Create a simple test image
    img = Image.new("RGB", (800, 600), color="red")
    img.save(image_path, "JPEG", quality=95)

    return image_path


@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(
        email="test@example.com", username="testuser", hashed_password="hashed_password"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_group(test_db, test_user):
    """Create a test group."""
    group = Group(name="Test Group", description="A test group", owner_id=test_user.id)
    test_db.add(group)
    test_db.commit()
    test_db.refresh(group)
    return group


@pytest.fixture
def test_meeting(test_db, test_group):
    """Create a test meeting."""
    meeting = Meeting(
        group_id=test_group.id, title="Test Meeting", description="A test meeting"
    )
    test_db.add(meeting)
    test_db.commit()
    test_db.refresh(meeting)
    return meeting


@pytest.fixture
def test_photo(test_db, test_group, test_user, test_meeting):
    """Create a test photo record."""
    photo = Photo(
        group_id=test_group.id,
        uploader_id=test_user.id,
        meeting_id=test_meeting.id,
        filename_orig="test_image.jpg",
        file_size=1024,
        file_hash="test_hash",
        mime_type="image/jpeg",
        is_processed=False,
    )
    test_db.add(photo)
    test_db.commit()
    test_db.refresh(photo)
    return photo


class TestThumbnailGeneration:
    """Test thumbnail generation functionality."""

    def test_create_image_thumbnail(self, test_image, temp_dir):
        """Test creating thumbnail from image."""
        thumb_path = create_thumbnail(test_image, size=(256, 256))

        assert thumb_path is not None
        assert thumb_path.exists()
        assert thumb_path.suffix == ".jpg"

        # Verify thumbnail dimensions
        with Image.open(thumb_path) as thumb:
            assert thumb.size[0] <= 256
            assert thumb.size[1] <= 256

    def test_create_thumbnail_nonexistent_file(self, temp_dir):
        """Test thumbnail creation with non-existent file."""
        fake_path = temp_dir / "nonexistent.jpg"
        thumb_path = create_thumbnail(fake_path)

        assert thumb_path is None

    @patch("subprocess.run")
    def test_create_video_thumbnail(self, mock_subprocess, temp_dir):
        """Test creating thumbnail from video file."""
        # Create a fake video file
        video_path = temp_dir / "test_video.mp4"
        video_path.write_bytes(b"fake video content")

        # Mock successful ffmpeg execution
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Create a fake thumbnail that ffmpeg would create
        expected_thumb = temp_dir / "thumb_12345678.jpg"

        with patch("backend.app.core.thumbs.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "1234567890abcdef"

            # Mock the thumbnail file creation
            with patch.object(Path, "exists", return_value=True):
                thumb_path = create_thumbnail(video_path)

                assert mock_subprocess.called
                # Verify ffmpeg was called with correct parameters
                call_args = mock_subprocess.call_args[0][0]
                assert "ffmpeg" in call_args
                assert str(video_path) in call_args


class TestWorkerTasks:
    """Test background worker task functionality."""

    @patch("backend.app.worker_tasks.Session")
    @patch("backend.app.worker_tasks.extract_exif")
    @patch("backend.app.worker_tasks.create_thumbnail")
    @patch("backend.app.worker_tasks.cluster_photos_into_meetings")
    def test_process_photo_success(
        self,
        mock_cluster,
        mock_thumbnail,
        mock_exif,
        mock_session,
        test_image,
        test_photo,
    ):
        """Test successful photo processing."""
        # Setup mocks
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance
        mock_session_instance.get.return_value = test_photo

        mock_exif.return_value = {
            "datetime": datetime.now(),
            "gps_point": None,
            "camera_make": "Test Camera",
        }

        mock_thumbnail.return_value = Path("thumb_test.jpg")

        # Execute task
        result = process_photo(str(test_photo.id), str(test_image))

        # Verify success
        assert result is True
        mock_exif.assert_called_once()
        mock_thumbnail.assert_called_once()
        mock_session_instance.commit.assert_called()

    @patch("backend.app.worker_tasks.Session")
    def test_process_photo_not_found(self, mock_session, test_image):
        """Test processing non-existent photo."""
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance
        mock_session_instance.get.return_value = None

        result = process_photo("nonexistent-id", str(test_image))

        assert result is False

    def test_process_photo_file_not_found(self, test_photo):
        """Test processing with non-existent file."""
        result = process_photo(str(test_photo.id), "/nonexistent/file.jpg")

        assert result is False

    @patch("backend.app.worker_tasks.extract_exif")
    def test_extract_exif_data_success(
        self, mock_exif, test_db, test_photo, test_image
    ):
        """Test EXIF data extraction."""
        mock_exif.return_value = {
            "datetime": datetime(2023, 1, 1, 12, 0, 0),
            "camera_make": "Canon",
            "camera_model": "EOS R5",
        }

        result = _extract_exif_data(test_db, test_photo, test_image)

        assert result is True
        assert test_photo.exif_data is not None
        assert test_photo.shot_at == datetime(2023, 1, 1, 12, 0, 0)

    @patch("backend.app.worker_tasks.extract_exif")
    def test_extract_exif_data_failure(
        self, mock_exif, test_db, test_photo, test_image
    ):
        """Test EXIF extraction failure."""
        mock_exif.side_effect = Exception("EXIF extraction failed")

        result = _extract_exif_data(test_db, test_photo, test_image)

        assert result is False

    @patch("backend.app.worker_tasks.create_thumbnail")
    def test_generate_thumbnail_success(
        self, mock_thumbnail, test_db, test_photo, test_image
    ):
        """Test thumbnail generation."""
        mock_thumbnail.return_value = Path("thumb_test.jpg")

        result = _generate_thumbnail(test_db, test_photo, test_image)

        assert result is True
        assert test_photo.filename_thumb == "thumb_test.jpg"

    @patch("backend.app.worker_tasks.create_thumbnail")
    def test_generate_thumbnail_failure(
        self, mock_thumbnail, test_db, test_photo, test_image
    ):
        """Test thumbnail generation failure."""
        mock_thumbnail.return_value = None

        result = _generate_thumbnail(test_db, test_photo, test_image)

        assert result is False


class TestRedisIntegration:
    """Test Redis queue integration."""

    def test_queue_connection_with_fake_redis(self):
        """Test Redis queue connection with fake Redis."""
        from rq import Queue
        from fakeredis import FakeRedis

        # Create fake Redis and queue
        fake_redis = FakeRedis()
        fake_queue = Queue("test", connection=fake_redis)

        # Test queue operations
        job = fake_queue.enqueue(lambda: "test")
        assert job is not None
        assert "<lambda>" in job.func_name


@pytest.mark.integration
class TestEndToEndProcessing:
    """Integration tests for complete photo processing pipeline."""

    @patch("backend.app.core.queues.redis_conn", FakeRedis())
    @patch("backend.app.worker_tasks.Session")
    def test_full_processing_pipeline(
        self, mock_session, test_image, test_photo, test_meeting
    ):
        """Test the complete photo processing pipeline."""
        from backend.app.core.queues import default_queue

        # Setup database mock
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance
        mock_session_instance.get.return_value = test_photo

        # Mock meeting for clustering
        test_photo.meeting_id = test_meeting.id
        mock_session_instance.get.side_effect = lambda model, id: {
            str(test_photo.id): test_photo,
            test_meeting.id: test_meeting,
        }.get(id)

        # Enqueue job
        job = default_queue.enqueue(
            process_photo, photo_id=str(test_photo.id), file_path=str(test_image)
        )

        assert job is not None

        # In a real scenario, the worker would process this job
        # For testing, we can verify the job was queued correctly
        assert job.func_name == "backend.app.worker_tasks.process_photo"
        assert job.args == (str(test_photo.id), str(test_image))
