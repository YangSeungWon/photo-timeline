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
    # Create database tables in development mode
    if settings.AUTO_CREATE_TABLES:
        logger.info("Auto-creating database tables...")
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created successfully!")


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
    """Health check endpoint."""
    return {"status": "healthy"}


# Placeholder for future routers
# from .routers import auth, groups, photos
#
# app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# app.include_router(groups.router, prefix="/groups", tags=["Groups"])
# app.include_router(photos.router, prefix="/photos", tags=["Photos"])
