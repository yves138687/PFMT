from fastapi import APIRouter

from app.api import auth, files, health, paths, settings


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(paths.router, prefix="/paths", tags=["paths"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
