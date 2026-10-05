"""
Tests for Phase 1: configuration, database, health endpoint.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import AIProvider, Environment, Settings, get_settings


# ===================================================================
# Configuration tests
# ===================================================================


class TestSettings:
    """Test the Settings configuration class."""

    def test_default_settings(self):
        """Defaults should be safe and functional."""
        settings = Settings(
            ai_provider="mock",
            database_url="sqlite:///./test.db",
        )
        assert settings.ai_provider == AIProvider.MOCK
        assert settings.max_upload_mb == 10
        assert settings.max_upload_bytes == 10 * 1024 * 1024
        assert settings.mandatory_weight == 2.0
        assert settings.recommended_weight == 1.0

    def test_cors_origin_parsing(self):
        """CORS origins should be parsed from a comma-separated string."""
        settings = Settings(
            cors_origins="http://localhost:3000, http://localhost:5173 ",
            ai_provider="mock",
            database_url="sqlite:///./test.db",
        )
        origins = settings.cors_origin_list
        assert origins == ["http://localhost:3000", "http://localhost:5173"]

    def test_cors_single_origin(self):
        settings = Settings(
            cors_origins="http://localhost:5173",
            ai_provider="mock",
            database_url="sqlite:///./test.db",
        )
        assert settings.cors_origin_list == ["http://localhost:5173"]

    def test_ai_provider_normalization(self):
        """AI provider string should be case-insensitive."""
        settings = Settings(
            ai_provider="MOCK",
            database_url="sqlite:///./test.db",
        )
        assert settings.ai_provider == AIProvider.MOCK

        settings2 = Settings(
            ai_provider="  Mock  ",
            database_url="sqlite:///./test.db",
        )
        assert settings2.ai_provider == AIProvider.MOCK

    def test_is_sqlite(self):
        settings = Settings(
            ai_provider="mock",
            database_url="sqlite:///./test.db",
        )
        assert settings.is_sqlite is True

    def test_is_not_sqlite(self):
        settings = Settings(
            ai_provider="mock",
            database_url="postgresql://user:pass@localhost/db",
        )
        assert settings.is_sqlite is False

    def test_validate_openai_key_missing(self):
        settings = Settings(
            ai_provider="openai",
            openai_api_key="",
            database_url="sqlite:///./test.db",
        )
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            settings.validate_ai_keys()

    def test_validate_openai_key_present(self):
        settings = Settings(
            ai_provider="openai",
            openai_api_key="sk-test-key",
            database_url="sqlite:///./test.db",
        )
        settings.validate_ai_keys()  # Should not raise

    def test_validate_gemini_key_missing(self):
        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="",
            database_url="sqlite:///./test.db",
        )
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            settings.validate_ai_keys()

    def test_validate_gemini_key_present(self):
        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="test-gemini-key",
            database_url="sqlite:///./test.db",
        )
        settings.validate_ai_keys()  # Should not raise

    def test_validate_mock_no_keys_needed(self):
        settings = Settings(
            ai_provider="mock",
            database_url="sqlite:///./test.db",
        )
        settings.validate_ai_keys()  # Should not raise

    def test_max_upload_bytes_custom(self):
        settings = Settings(
            ai_provider="mock",
            database_url="sqlite:///./test.db",
            max_upload_mb=25,
        )
        assert settings.max_upload_bytes == 25 * 1024 * 1024


# ===================================================================
# Health endpoint tests
# ===================================================================


class TestHealthEndpoint:
    """Test the /api/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient):
        """Health check should return 200 with status info."""
        response = await client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_shows_database_status(self, client: AsyncClient):
        """Health check should include database status."""
        response = await client.get("/api/health")
        data = response.json()

        assert "components" in data
        assert "database" in data["components"]
        assert data["components"]["database"]["status"] == "healthy"
        assert data["components"]["database"]["error"] is None

    @pytest.mark.asyncio
    async def test_health_shows_ai_provider(self, client: AsyncClient):
        """Health check should show the configured AI provider."""
        response = await client.get("/api/health")
        data = response.json()

        ai = data["components"]["ai_provider"]
        assert ai["provider"] == "mock"
        assert ai["status"] == "configured"

    @pytest.mark.asyncio
    async def test_health_shows_environment(self, client: AsyncClient):
        """Health check should indicate the environment."""
        response = await client.get("/api/health")
        data = response.json()
        assert data["environment"] in ["development", "testing", "production"]



class TestDatabaseConnection:
    """Test database URL conversion and connectivity."""

    def test_build_async_url_sqlite(self):
        from app.database import _build_async_url

        assert _build_async_url("sqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"

    def test_build_async_url_postgresql(self):
        from app.database import _build_async_url

        result = _build_async_url("postgresql://user:pass@localhost/db")
        assert result == "postgresql+asyncpg://user:pass@localhost/db"

    def test_build_async_url_already_async(self):
        from app.database import _build_async_url

        url = "sqlite+aiosqlite:///./test.db"
        assert _build_async_url(url) == url

        url2 = "postgresql+asyncpg://user:pass@localhost/db"
        assert _build_async_url(url2) == url2

    @pytest.mark.asyncio
    async def test_db_session_works(self, db_session):
        """The test DB session should be functional."""
        from sqlalchemy import text

        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1


class TestErrorFormat:
    """Test that errors follow the consistent format."""

    @pytest.mark.asyncio
    async def test_404_error_format(self, client: AsyncClient):
        """Unknown routes should return consistent error format."""
        response = await client.get("/api/nonexistent")
        assert response.status_code in [404, 405]
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
