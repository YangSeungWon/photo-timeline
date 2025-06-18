import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

import sys
import os

sys.path.append(os.path.dirname(__file__))

from app.core.config import settings
from app.core.database import engine
from app.api import api_router

# Import all models to register them with SQLModel metadata
from app.models.user import User
# Import other models here as they are created
# from app.models.group import Group
# from app.models.photo import Photo

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- App Initialization ---
app = FastAPI(
    title="Photo Timeline API",
    description="A closed-network web service for photo sharing within groups",
    version="1.0.0",
)

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Photo Timeline API...")
    
    # Import here to avoid circular imports
    from app.core.database import engine
    
    # Create database tables if database is available
    if settings.AUTO_CREATE_TABLES:
        if engine:
            try:
                logger.info("Auto-creating database tables...")
                SQLModel.metadata.create_all(engine)
                logger.info("Database tables created successfully!")
            except Exception as e:
                logger.error(f"Failed to create database tables: {e}")
                logger.error("Database functionality may not work properly.")
        else:
            logger.warning("Database engine not available. Skipping table creation.")
            logger.warning("Please check database connection and restart the service.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Photo Timeline API...")


# --- API Endpoints ---
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Photo Timeline API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint with database status."""
    from app.core.database import engine
    from sqlalchemy import text
    
    status = {"status": "healthy", "database": "unknown"}
    
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            status["database"] = "connected"
        except Exception as e:
            status["database"] = f"error: {str(e)}"
            status["status"] = "degraded"
    else:
        status["database"] = "not_available"
        status["status"] = "degraded"
    
    return status


# Placeholder for future routers
# from .routers import auth, groups, photos
#
# app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# app.include_router(groups.router, prefix="/groups", tags=["Groups"])
# app.include_router(photos.router, prefix="/photos", tags=["Photos"])
