"""Server info endpoint — used by Tauri Android client for discovery."""

from fastapi import APIRouter, Request

from app.infrastructure.config import Settings

router = APIRouter()


@router.get("/api/server-info")
async def server_info(request: Request) -> dict:
    """Return base URL and version for client discovery."""
    settings = Settings.from_env()
    base_url = str(request.base_url).rstrip("/")
    return {
        "url": base_url,
        "version": settings.version,
    }
