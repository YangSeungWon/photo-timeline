from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel
from typing import Iterator

from .config import settings


# Create engine with connection pooling and health checks
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


def create_db_and_tables():
    """Create database tables. Used in development mode."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session
