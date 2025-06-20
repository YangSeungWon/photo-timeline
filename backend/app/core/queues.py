import logging
from redis import Redis
from rq import Queue, Connection

from .config import settings

logger = logging.getLogger(__name__)

# Redis connection
redis_conn = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=False,
)

# Default queue for background tasks (photo processing, thumbnails, etc.)
default_queue = Queue("default", connection=redis_conn)

# Dedicated queue for clustering operations (prevents congestion during burst uploads)
cluster_queue = Queue("cluster", connection=redis_conn)


def get_queue() -> Queue:
    """Get the default queue for background tasks."""
    return default_queue


def get_cluster_queue() -> Queue:
    """Get the dedicated cluster queue for photo clustering operations."""
    return cluster_queue


def test_redis_connection() -> bool:
    """Test Redis connection."""
    try:
        redis_conn.ping()
        logger.info("Redis connection successful")
        return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return False
