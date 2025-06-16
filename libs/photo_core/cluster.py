import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_MEETING_GAP_HOURS = 4


def cluster_photos_into_meetings(
    photos: List[Dict[str, Any]],
    gap_hours: int = DEFAULT_MEETING_GAP_HOURS,
) -> List[Dict[str, Any]]:
    """
    Groups photos into meetings based on a time gap and assigns meeting IDs.

    Args:
        photos: A list of photo dictionaries, each with a 'DateTimeOriginal' key.
        gap_hours: The maximum time difference in hours to be considered
                   part of the same meeting.

    Returns:
        A list of photo dictionaries with 'meeting_id' and 'meeting_date' added.
        Photos without timestamps will have meeting_id=None.
    """
    if not photos:
        return []

    # Separate photos with and without timestamps
    dated_photos = []
    undated_photos = []

    for photo in photos:
        timestamp = photo.get("DateTimeOriginal")
        if timestamp:
            # Ensure timestamp is a datetime object
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.strptime(timestamp, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    logger.warning(f"Could not parse timestamp: {timestamp}")
                    undated_photos.append(
                        {**photo, "meeting_id": None, "meeting_date": None}
                    )
                    continue

            dated_photos.append({**photo, "DateTimeOriginal": timestamp})
        else:
            undated_photos.append({**photo, "meeting_id": None, "meeting_date": None})

    if not dated_photos:
        return undated_photos

    # Sort photos chronologically
    dated_photos.sort(key=lambda p: p["DateTimeOriginal"])

    # Group into meetings
    meetings = []
    current_meeting = [dated_photos[0]]
    time_gap = timedelta(hours=gap_hours)

    for i in range(1, len(dated_photos)):
        prev_photo = dated_photos[i - 1]
        current_photo = dated_photos[i]

        prev_time = prev_photo["DateTimeOriginal"]
        current_time = current_photo["DateTimeOriginal"]

        if current_time - prev_time > time_gap:
            # Finish the current meeting and start a new one
            meetings.append(current_meeting)
            current_meeting = [current_photo]
        else:
            current_meeting.append(current_photo)

    # Add the last meeting
    if current_meeting:
        meetings.append(current_meeting)

    # Assign meeting IDs and dates
    result_photos = []

    for meeting in meetings:
        meeting_id = str(uuid4())
        # Use the date of the first photo in the meeting
        meeting_date = meeting[0]["DateTimeOriginal"].date()

        for photo in meeting:
            result_photos.append(
                {**photo, "meeting_id": meeting_id, "meeting_date": meeting_date}
            )

    # Add undated photos
    result_photos.extend(undated_photos)

    logger.info(f"Clustered {len(dated_photos)} photos into {len(meetings)} meetings")

    return result_photos


def generate_meeting_track(photos: List[Dict[str, Any]]) -> Optional[List[List[float]]]:
    """
    Generates a GPS track (list of [lat, lon] coordinates) for a meeting.

    Args:
        photos: List of photos from the same meeting, sorted by timestamp.

    Returns:
        A list of [latitude, longitude] coordinates, or None if no GPS data.
    """
    track_points = []

    for photo in photos:
        lat = photo.get("GPSLat")
        lon = photo.get("GPSLong")

        if lat is not None and lon is not None:
            track_points.append([float(lat), float(lon)])

    return track_points if track_points else None
