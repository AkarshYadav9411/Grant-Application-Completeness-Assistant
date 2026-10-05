"""
Grant Application Completeness Assistant — FastAPI entry point.

This is an evidence-based review assistant. It does NOT make authoritative
legal or funding-eligibility decisions.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import close_db, init_db
from app.routers import documents, evidence, health, projects, requirements
from app.utils.errors import (
    generic_exception_handler,
    http_exception_handler,
    starlette_http_exception_handler,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    settings = get_settings()

    # Startup
    logger.info("Starting Grant Application Completeness Assistant")
    logger.info("Environment: %s", settings.app_env.value)
    logger.info("AI Provider: %s", settings.ai_provider.value)
    logger.info("Database: %s", "SQLite" if settings.is_sqlite else "PostgreSQL")

    # Ensure upload directory exists
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Upload directory: %s", settings.upload_dir)

    # Initialize database tables (dev mode; production should use Alembic)
    await init_db()
    logger.info("Database tables initialized")

    # Validate AI keys (warn, don't crash)
    try:
        settings.validate_ai_keys()
        logger.info("AI provider keys validated")
    except ValueError as e:
        logger.warning("AI provider configuration: %s", e)

    yield

    # Shutdown
    logger.info("Shutting down")
    await close_db()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Grant Application Completeness Assistant",
        description=(
            "An evidence-based review assistant that helps grant applicants "
            "determine how complete their draft application is against a "
            "provided grant guideline. This tool does NOT make authoritative "
            "legal or funding-eligibility decisions."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Routers
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(documents.router)
    app.include_router(requirements.router)
    app.include_router(evidence.router)

    return app


app = create_app()
