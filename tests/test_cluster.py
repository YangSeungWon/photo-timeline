import pytest
from datetime import datetime, timedelta
from photo_core.cluster import (
    cluster_photos_into_meetings,
    generate_meeting_track,
    DEFAULT_MEETING_GAP_HOURS,
)


class TestClusterPhotosIntoMeetings:
    def test_cluster_empty_list(self):
        """Test clustering with empty photo list."""
        result = cluster_photos_into_meetings([])
        assert result == []

    def test_cluster_no_timestamps(self):
        """Test clustering with photos that have no timestamps."""
        photos = [
            {"FileName": "IMG_001.jpg", "DateTimeOriginal": None},
            {"FileName": "IMG_002.jpg", "DateTimeOriginal": None},
        ]

        result = cluster_photos_into_meetings(photos)

        assert len(result) == 2
        for photo in result:
            assert photo["meeting_id"] is None
            assert photo["meeting_date"] is None

    def test_cluster_single_meeting(self):
        """Test clustering photos that should be in one meeting."""
        photos = [
            {
                "FileName": "IMG_001.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 14, 0, 0),
            },
            {
                "FileName": "IMG_002.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 14, 30, 0),
            },
            {
                "FileName": "IMG_003.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 15, 0, 0),
            },
        ]

        result = cluster_photos_into_meetings(photos)

        assert len(result) == 3
        # All photos should have the same meeting_id
        meeting_ids = {photo["meeting_id"] for photo in result}
        assert len(meeting_ids) == 1
        assert None not in meeting_ids

        # All photos should have the same meeting_date
        meeting_dates = {photo["meeting_date"] for photo in result}
        assert len(meeting_dates) == 1
        assert list(meeting_dates)[0] == datetime(2025, 6, 10).date()

    def test_cluster_two_meetings(self):
        """Test clustering photos that should be in two separate meetings."""
        photos = [
            {
                "FileName": "IMG_001.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 9, 0, 0),
            },
            {
                "FileName": "IMG_002.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 10, 0, 0),
            },
            # 6-hour gap (> 4 hour default)
            {
                "FileName": "IMG_003.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 16, 0, 0),
            },
            {
                "FileName": "IMG_004.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 17, 0, 0),
            },
        ]

        result = cluster_photos_into_meetings(photos)

        assert len(result) == 4
        # Should have exactly 2 different meeting IDs
        meeting_ids = {photo["meeting_id"] for photo in result if photo["meeting_id"]}
        assert len(meeting_ids) == 2

    def test_cluster_custom_gap(self):
        """Test clustering with custom time gap."""
        photos = [
            {
                "FileName": "IMG_001.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 9, 0, 0),
            },
            {
                "FileName": "IMG_002.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 10, 0, 0),
            },
            # 2-hour gap
            {
                "FileName": "IMG_003.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 12, 0, 0),
            },
        ]

        # With 1-hour gap, should create 2 meetings
        result = cluster_photos_into_meetings(photos, gap_hours=1)
        meeting_ids = {photo["meeting_id"] for photo in result if photo["meeting_id"]}
        assert len(meeting_ids) == 2

        # With 3-hour gap, should create 1 meeting
        result = cluster_photos_into_meetings(photos, gap_hours=3)
        meeting_ids = {photo["meeting_id"] for photo in result if photo["meeting_id"]}
        assert len(meeting_ids) == 1

    def test_cluster_string_timestamps(self):
        """Test clustering with string timestamp format."""
        photos = [
            {"FileName": "IMG_001.jpg", "DateTimeOriginal": "2025:06:10 14:00:00"},
            {"FileName": "IMG_002.jpg", "DateTimeOriginal": "2025:06:10 15:00:00"},
        ]

        result = cluster_photos_into_meetings(photos)

        assert len(result) == 2
        meeting_ids = {photo["meeting_id"] for photo in result if photo["meeting_id"]}
        assert len(meeting_ids) == 1

    def test_cluster_mixed_valid_invalid_timestamps(self):
        """Test clustering with mix of valid and invalid timestamps."""
        photos = [
            {
                "FileName": "IMG_001.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 14, 0, 0),
            },
            {"FileName": "IMG_002.jpg", "DateTimeOriginal": "invalid-date-format"},
            {"FileName": "IMG_003.jpg", "DateTimeOriginal": None},
        ]

        result = cluster_photos_into_meetings(photos)

        assert len(result) == 3
        # Only one photo should have a meeting_id
        photos_with_meeting = [p for p in result if p["meeting_id"] is not None]
        assert len(photos_with_meeting) == 1

        # Two photos should have no meeting_id
        photos_without_meeting = [p for p in result if p["meeting_id"] is None]
        assert len(photos_without_meeting) == 2


class TestGenerateMeetingTrack:
    def test_generate_track_with_gps(self):
        """Test track generation with GPS coordinates."""
        photos = [
            {"FileName": "IMG_001.jpg", "GPSLat": 37.7749, "GPSLong": -122.4194},
            {"FileName": "IMG_002.jpg", "GPSLat": 37.7849, "GPSLong": -122.4094},
        ]

        track = generate_meeting_track(photos)

        assert track is not None
        assert len(track) == 2
        assert track[0] == [37.7749, -122.4194]
        assert track[1] == [37.7849, -122.4094]

    def test_generate_track_no_gps(self):
        """Test track generation with no GPS coordinates."""
        photos = [
            {"FileName": "IMG_001.jpg", "GPSLat": None, "GPSLong": None},
            {"FileName": "IMG_002.jpg"},
        ]

        track = generate_meeting_track(photos)

        assert track is None

    def test_generate_track_partial_gps(self):
        """Test track generation with some photos having GPS."""
        photos = [
            {"FileName": "IMG_001.jpg", "GPSLat": 37.7749, "GPSLong": -122.4194},
            {"FileName": "IMG_002.jpg", "GPSLat": None, "GPSLong": None},
            {"FileName": "IMG_003.jpg", "GPSLat": 37.7849, "GPSLong": -122.4094},
        ]

        track = generate_meeting_track(photos)

        assert track is not None
        assert len(track) == 2  # Only photos with GPS
        assert track[0] == [37.7749, -122.4194]
        assert track[1] == [37.7849, -122.4094]

    def test_generate_track_empty_list(self):
        """Test track generation with empty photo list."""
        track = generate_meeting_track([])
        assert track is None
