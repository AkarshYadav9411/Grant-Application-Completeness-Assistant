"""
Shared pytest fixtures for the test suite.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import create_app
import app.models  # noqa: F401 - ensure all models are registered in Base.metadata


# ---------------------------------------------------------------------------
# Test database engine (in-memory SQLite)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean in-memory database session for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ---------------------------------------------------------------------------
# Test HTTP client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, tmp_path) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP test client with the DB dependency overridden."""
    # Force mock AI provider and test environment
    os.environ["AI_PROVIDER"] = "mock"
    os.environ["APP_ENV"] = "testing"
    os.environ["APP_DEBUG"] = "false"

    app = create_app()

    # Override the DB dependency to use the test in-memory session
    async def override_get_db():
        yield db_session

    def override_get_settings():
        return Settings(
            app_env="testing",
            app_debug=False,
            ai_provider="mock",
            database_url="sqlite+aiosqlite:///:memory:",
            upload_dir=tmp_path / "uploads",
            max_upload_mb=1,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
