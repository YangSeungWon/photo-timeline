# Photo Core Library

Core utilities for EXIF extraction, photo clustering, and timestamp suggestions for the Photo-Timeline project.

## Features

- **EXIF Extraction**: Extract date/time and GPS coordinates from JPEG, PNG, TIFF, HEIC, and video files
- **Photo Clustering**: Group photos into "meetings" based on time gaps (default: 4 hours)
- **Timestamp Suggestions**: Generate prev+1s, middle, and next-1s timestamp suggestions for photos without dates
- **GPS Track Generation**: Create GPS tracks from photo coordinates

## Installation

```bash
pip install -e .
```

## Usage

### EXIF Extraction

```python
from photo_core import extract_exif
from pathlib import Path

# Extract EXIF data from a photo
metadata = extract_exif(Path("photo.jpg"))
print(metadata["DateTimeOriginal"])  # datetime object
print(metadata["GPSLat"], metadata["GPSLong"])  # GPS coordinates
```

### Photo Clustering

```python
from photo_core import cluster_photos_into_meetings

photos = [
    {"FileName": "IMG_001.jpg", "DateTimeOriginal": datetime(2025, 6, 10, 9, 0, 0)},
    {"FileName": "IMG_002.jpg", "DateTimeOriginal": datetime(2025, 6, 10, 10, 0, 0)},
    # 6-hour gap
    {"FileName": "IMG_003.jpg", "DateTimeOriginal": datetime(2025, 6, 10, 16, 0, 0)},
]

# Cluster into meetings (default 4-hour gap)
clustered = cluster_photos_into_meetings(photos)
# Each photo now has meeting_id and meeting_date fields
```

### Timestamp Suggestions

```python
from photo_core import suggest_timestamps

photos = [
    {"FileName": "IMG_001.jpg", "DateTimeOriginal": datetime(2025, 6, 10, 14, 0, 0)},
    {"FileName": "IMG_003.jpg", "DateTimeOriginal": datetime(2025, 6, 10, 16, 0, 0)},
]

# Get suggestions for IMG_002.jpg
prev_plus, middle, next_minus = suggest_timestamps(photos, "IMG_002.jpg")
# prev_plus: 2025-06-10 14:00:01
# middle: 2025-06-10 15:00:00
# next_minus: 2025-06-10 15:59:59
```

## Dependencies

- Pillow >= 9.0
- piexif >= 1.1
- exiftool (optional, for HEIC and video files)

## Testing

```bash
pytest
```
