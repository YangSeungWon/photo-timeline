from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from fastapi import HTTPException

from .config import settings

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True
)
def create_database_engine():
    """Create database engine with retry logic."""
    logger.info(f"Attempting to connect to database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'hidden'}")
    
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_recycle=300,  # Recycle connections every 5 minutes
        pool_size=10,
        max_overflow=20,
    )
    
    # Test the connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        logger.info("Database connection successful!")
    
    return engine

# Create engine with the updated settings
try:
    engine = create_database_engine()
except Exception as e:
    logger.error(f"Failed to create database engine after retries: {e}")
    # Create a dummy engine for graceful degradation
    engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def get_db():
    """Get database session."""
    if not engine or not SessionLocal:
        raise HTTPException(
            status_code=503,
            detail="Database is temporarily unavailable. Please try again later."
        )
        
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.close()
