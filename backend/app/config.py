"""
Application configuration loaded from environment variables.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class AIProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    MOCK = "mock"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Application
    app_env: Environment = Environment.DEVELOPMENT
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = "sqlite:///./grant_assistant.db"

    # AI Provider
    ai_provider: AIProvider = AIProvider.MOCK
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    ai_timeout_seconds: int = 45

    # Upload settings
    max_upload_mb: int = 10

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Scoring weights (configurable constants per spec §16)
    mandatory_weight: float = 2.0
    recommended_weight: float = 1.0

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @field_validator("ai_provider", mode="before")
    @classmethod
    def normalize_ai_provider(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower().strip()
        return v

    def validate_ai_keys(self) -> None:
        """Validate that the required API key is set for the chosen provider."""
        if self.ai_provider == AIProvider.OPENAI and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when AI_PROVIDER=openai. "
                "Set it in your .env file or use AI_PROVIDER=mock for offline development."
            )
        if self.ai_provider == AIProvider.GEMINI and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when AI_PROVIDER=gemini. "
                "Set it in your .env file or use AI_PROVIDER=mock for offline development."
            )


def get_settings() -> Settings:
    """Factory function to create settings. Supports .env from CWD or backend dir."""
    # Try loading .env from CWD first, then from backend dir, then project root
    for env_path in [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]:
        if env_path.exists():
            os.environ.setdefault("_ENV_FILE_PATH", str(env_path))
            return Settings(_env_file=str(env_path))
    return Settings()
