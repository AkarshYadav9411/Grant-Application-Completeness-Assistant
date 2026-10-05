"""
Health check router.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Health check endpoint.

    Returns application status, database connectivity, configured AI provider,
    and current timestamp.
    """
    # Check database connectivity
    db_status = "healthy"
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "unhealthy"
        db_error = str(e)

    # Check AI provider configuration
    ai_status = "configured"
    ai_message = None
    try:
        settings.validate_ai_keys()
    except ValueError as e:
        ai_status = "not_configured"
        ai_message = str(e)

    overall_status = "healthy" if db_status == "healthy" else "unhealthy"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "components": {
            "database": {
                "status": db_status,
                "error": db_error,
            },
            "ai_provider": {
                "provider": settings.ai_provider.value,
                "status": ai_status,
                "message": ai_message,
            },
        },
        "environment": settings.app_env.value,
    }
