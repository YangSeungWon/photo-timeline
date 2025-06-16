import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from photo_core.exif import (
    extract_exif,
    suggest_timestamps,
    _convert_gps_to_decimal,
)


class TestExtractExif:
    def test_extract_exif_unsupported_file(self, tmp_path):
        """Test that unsupported file types return basic metadata."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("not an image")

        result = extract_exif(test_file)

        assert result["FileName"] == "test.txt"
        assert result["FilePath"] == str(test_file)
        assert result["DateTimeOriginal"] is None
        assert result["GPSLat"] is None
        assert result["GPSLong"] is None

    @patch("libs.photo_core.exif.piexif.load")
    def test_extract_exif_jpeg_with_data(self, mock_piexif_load, tmp_path):
        """Test EXIF extraction from JPEG with date and GPS."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpeg data")

        # Mock EXIF data
        mock_exif_dict = {
            "Exif": {36867: b"2025:06:10 14:30:00"},  # DateTimeOriginal
            "GPS": {
                2: ((37, 1), (46, 1), (1234, 100)),  # GPSLatitude
                1: b"N",  # GPSLatitudeRef
                4: ((122, 1), (25, 1), (5678, 100)),  # GPSLongitude
                3: b"W",  # GPSLongitudeRef
            },
        }
        mock_piexif_load.return_value = mock_exif_dict

        result = extract_exif(test_file)

        assert result["FileName"] == "test.jpg"
        assert isinstance(result["DateTimeOriginal"], datetime)
        assert result["DateTimeOriginal"].year == 2025
        assert result["DateTimeOriginal"].month == 6
        assert result["DateTimeOriginal"].day == 10
        assert result["GPSLat"] is not None
        assert result["GPSLong"] is not None


class TestConvertGpsToDecimal:
    def test_convert_gps_valid_north_east(self):
        """Test GPS conversion for North/East coordinates."""
        gps_coord = ((37, 1), (46, 1), (1234, 100))  # 37°46'12.34"
        gps_ref = b"N"

        result = _convert_gps_to_decimal(gps_coord, gps_ref)

        expected = 37 + 46 / 60 + 12.34 / 3600
        assert abs(result - expected) < 0.0001

    def test_convert_gps_valid_south_west(self):
        """Test GPS conversion for South/West coordinates."""
        gps_coord = ((37, 1), (46, 1), (1234, 100))
        gps_ref = b"S"

        result = _convert_gps_to_decimal(gps_coord, gps_ref)

        expected = -(37 + 46 / 60 + 12.34 / 3600)
        assert abs(result - expected) < 0.0001

    def test_convert_gps_invalid_data(self):
        """Test GPS conversion with invalid data."""
        assert _convert_gps_to_decimal(None, b"N") is None
        assert _convert_gps_to_decimal(((37, 1),), b"N") is None
        assert _convert_gps_to_decimal(((37, 1), (46, 1), (1234, 100)), None) is None


class TestSuggestTimestamps:
    def test_suggest_timestamps_with_prev_and_next(self):
        """Test timestamp suggestions with both previous and next photos."""
        photos = [
            {
                "FileName": "IMG_001.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 14, 0, 0),
            },
            {
                "FileName": "IMG_003.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 16, 0, 0),
            },
        ]

        prev_plus, middle, next_minus = suggest_timestamps(photos, "IMG_002.jpg")

        assert prev_plus == datetime(2025, 6, 10, 14, 0, 1)  # prev + 1s
        assert middle == datetime(2025, 6, 10, 15, 0, 0)  # middle
        assert next_minus == datetime(2025, 6, 10, 15, 59, 59)  # next - 1s

    def test_suggest_timestamps_only_prev(self):
        """Test timestamp suggestions with only previous photo."""
        photos = [
            {
                "FileName": "IMG_001.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 14, 0, 0),
            }
        ]

        prev_plus, middle, next_minus = suggest_timestamps(photos, "IMG_002.jpg")

        assert prev_plus == datetime(2025, 6, 10, 14, 0, 1)
        assert middle is None
        assert next_minus is None

    def test_suggest_timestamps_only_next(self):
        """Test timestamp suggestions with only next photo."""
        photos = [
            {
                "FileName": "IMG_002.jpg",
                "DateTimeOriginal": datetime(2025, 6, 10, 16, 0, 0),
            }
        ]

        prev_plus, middle, next_minus = suggest_timestamps(photos, "IMG_001.jpg")

        assert prev_plus is None
        assert middle is None
        assert next_minus == datetime(2025, 6, 10, 15, 59, 59)

    def test_suggest_timestamps_no_adjacent_photos(self):
        """Test timestamp suggestions with no adjacent photos."""
        photos = []

        prev_plus, middle, next_minus = suggest_timestamps(photos, "IMG_001.jpg")

        assert prev_plus is None
        assert middle is None
        assert next_minus is None

    def test_suggest_timestamps_string_dates(self):
        """Test timestamp suggestions with string date formats."""
        photos = [
            {"FileName": "IMG_001.jpg", "DateTimeOriginal": "2025:06:10 14:00:00"},
            {"FileName": "IMG_003.jpg", "DateTimeOriginal": "2025:06:10 16:00:00"},
        ]

        prev_plus, middle, next_minus = suggest_timestamps(photos, "IMG_002.jpg")

        assert prev_plus == datetime(2025, 6, 10, 14, 0, 1)
        assert middle == datetime(2025, 6, 10, 15, 0, 0)
        assert next_minus == datetime(2025, 6, 10, 15, 59, 59)
