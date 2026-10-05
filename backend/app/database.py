"""
Database engine, session management, and base model for SQLAlchemy 2.x.
Compatible with both SQLite (dev) and PostgreSQL (prod).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def _build_async_url(url: str) -> str:
    """Convert a sync database URL to an async one."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("sqlite+aiosqlite:///"):
        return url
    return url


def _get_engine(database_url: str | None = None):
    """Create the async engine. Accepts an optional override URL for testing."""
    settings = get_settings()
    url = database_url or settings.database_url
    async_url = _build_async_url(url)

    connect_args = {}
    if "sqlite" in async_url:
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        async_url,
        echo=settings.app_debug and settings.app_env.value == "development",
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if "sqlite" in async_url:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# Default engine and session factory
engine = _get_engine()
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables. Used in development; production should use Alembic."""
    import app.models  # noqa: F401 - ensure all models are registered with Base.metadata

    async with engine.begin() as conn:
        # Enable WAL mode for SQLite for better concurrent access
        settings = get_settings()
        if settings.is_sqlite:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    await engine.dispose()
