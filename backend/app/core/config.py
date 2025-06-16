import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/phototimeline"
    AUTO_CREATE_TABLES: bool = False

    # JWT Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # File Storage
    UPLOAD_DIR: str = "./uploads"
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
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
