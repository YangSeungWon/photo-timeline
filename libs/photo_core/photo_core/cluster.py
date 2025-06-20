import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MEETING_GAP_HOURS = 18


def cluster_photos_into_meetings(
    photos: List[Dict[str, Any]],
    gap_hours: int = DEFAULT_MEETING_GAP_HOURS,
) -> List[Dict[str, Any]]:
    """
    Groups photos into meetings based on a time gap using single-pass O(n) algorithm.
    
    핵심: "이미 모인 클러스터는 다시 검사하지 않는다"
    - 한 번만 스캔(O(n))으로 끝남
    - 클러스터 수만큼만 미팅 레코드가 생김

    Args:
        photos: A list of photo dictionaries, each with a 'DateTimeOriginal' key.
        gap_hours: The maximum time difference in hours to be considered
                   part of the same meeting.

    Returns:
        A list of photo dictionaries with 'meeting_date' added.
        Photos without timestamps will have meeting_date=None.
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
                    undated_photos.append({**photo, "meeting_date": None})
                    continue

            dated_photos.append({**photo, "DateTimeOriginal": timestamp})
        else:
            undated_photos.append({**photo, "meeting_date": None})

    if not dated_photos:
        return undated_photos

    # Sort photos chronologically (핵심: 정렬 누락 방지)
    dated_photos.sort(key=lambda p: p["DateTimeOriginal"])

    # Single-pass clustering (O(n) 보장)
    MEETING_GAP = timedelta(hours=gap_hours)
    meetings = []
    current = [dated_photos[0]]  # 진행 중인 클러스터

    # zip(photos, photos[1:]) 패턴으로 단일 패스
    for prev, nxt in zip(dated_photos, dated_photos[1:]):
        if nxt["DateTimeOriginal"] - prev["DateTimeOriginal"] <= MEETING_GAP:
            current.append(nxt)  # 같은 미팅
        else:
            meetings.append(current)  # 현재 클러스터 완료
            current = [nxt]  # 새 미팅 시작
    
    meetings.append(current)  # 마지막 클러스터

    # Assign meeting dates (meeting_id는 백엔드에서 처리)
    result_photos = []
    
    for meeting_cluster in meetings:
        # Use the date of the first photo in the meeting
        meeting_date = meeting_cluster[0]["DateTimeOriginal"].date()
        
        for photo in meeting_cluster:
            result_photos.append({**photo, "meeting_date": meeting_date})

    # Add undated photos
    result_photos.extend(undated_photos)

    logger.info(f"Clustered {len(dated_photos)} photos into {len(meetings)} meetings using single-pass algorithm")

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
