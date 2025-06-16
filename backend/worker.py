#!/usr/bin/env python3
"""
RQ Worker for background photo processing tasks.

This worker processes photos uploaded to the system by:
1. Extracting EXIF metadata
2. Clustering photos into meetings
3. Generating thumbnails
4. Updating database records

Usage:
    python worker.py
"""

import os
import sys
import logging
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from rq import Worker, Connection
from app.core.queues import redis_conn, test_redis_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("worker")


def main():
    """Main worker function."""
    logger.info("Starting RQ worker...")

    # Test Redis connection
    if not test_redis_connection():
        logger.error("Failed to connect to Redis. Exiting.")
        sys.exit(1)

    # Queues to listen to
    listen = ["default"]

    logger.info(f"Worker listening to queues: {listen}")

    try:
        with Connection(redis_conn):
            worker = Worker(listen, name=f"worker-{os.getpid()}")
            logger.info(f"Worker {worker.name} started")
            worker.work(with_scheduler=False)
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
