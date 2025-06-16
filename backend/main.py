import logging

from fastapi import FastAPI

import sys
import os

sys.path.append(os.path.dirname(__file__))

from app.core.config import settings
from app.core.database import create_db_and_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- App Initialization ---
app = FastAPI(
    title="Photo-Timeline API",
    description="API for the Photo-Timeline web service.",
    version="0.1.0",
)


# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Photo-Timeline API...")
    # Create database tables in development mode
    if settings.auto_create_tables:
        logger.info("Auto-creating database tables...")
        create_db_and_tables()
        logger.info("Database tables created successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Photo-Timeline API...")
    # Here you would close DB connections, etc.
    pass


# --- API Endpoints ---
@app.get("/", tags=["Health Check"])
async def read_root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Welcome to Photo-Timeline!"}


# Placeholder for future routers
# from .routers import auth, groups, photos
#
# app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# app.include_router(groups.router, prefix="/groups", tags=["Groups"])
# app.include_router(photos.router, prefix="/photos", tags=["Photos"])
