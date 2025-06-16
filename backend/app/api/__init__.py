from fastapi import APIRouter

from .auth import router as auth_router
from .groups import router as groups_router
from .photos import router as photos_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(groups_router, prefix="/groups", tags=["groups"])
api_router.include_router(photos_router, prefix="/photos", tags=["photos"])
