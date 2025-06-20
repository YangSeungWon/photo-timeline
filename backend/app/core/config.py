import os
import secrets
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/phototimeline"
    AUTO_CREATE_TABLES: bool = True

    # JWT Authentication - 보안상 중요한 설정
    SECRET_KEY: str = Field(default="", description="JWT secret key - should be set in .env file")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Redis - 환경변수 우선 사용
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # File Storage
    UPLOAD_DIR: str = "/srv/photo-timeline/storage"  # Docker 볼륨 경로
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: set = {
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".heic",
        ".mov",
        ".mp4",
    }

    # Thumbnail settings
    THUMBNAIL_SIZE: tuple = (512, 512)
    THUMBNAIL_QUALITY: int = 85

    # Development settings
    DEBUG: bool = False

    # Photo clustering settings
    MEETING_GAP_HOURS: int = 18  # Time gap in hours for meeting clustering
    
    # Debounce settings for batch clustering (production tuned)
    CLUSTER_DEBOUNCE_TTL: int = 5    # Seconds to wait for quiet period (3-8s sweet spot)
    CLUSTER_RETRY_DELAY: int = 3     # Seconds to delay first clustering attempt (TTL ÷ 2)
    CLUSTER_MAX_RETRIES: int = 3     # Maximum retry attempts for failed clustering
    
    # Metrics and monitoring
    ENABLE_CLUSTERING_METRICS: bool = True  # Enable StatsD/Prometheus metrics

    # Frontend URL for email links
    FRONTEND_URL: str = "http://localhost:3067"

    # Email settings - 환경변수로만 설정
    MAIL_HOST: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USER: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_SECURE: bool = True  # Use TLS
    MAIL_FROM: str = ""
    MAIL_FROM_NAME: str = "Photo Timeline"

    def __post_init__(self):
        """Validate settings after initialization."""
        if not self.SECRET_KEY:
            print("WARNING: SECRET_KEY not set in .env file. Generating a temporary one.")
            print("For production, please set SECRET_KEY in your .env file.")
            self.SECRET_KEY = secrets.token_urlsafe(32)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
