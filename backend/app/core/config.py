from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost/phototimeline"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Development settings
    auto_create_tables: bool = False
    debug: bool = False

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # File storage
    storage_path: str = "/srv/photo-timeline/storage"
    max_file_size: int = 50 * 1024 * 1024  # 50MB

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
