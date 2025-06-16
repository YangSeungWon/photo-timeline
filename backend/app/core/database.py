from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from .config import settings

# Create engine with the updated settings
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Get database session."""
    with Session(engine) as session:
        yield session
