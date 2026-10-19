from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives at <repo>/backend/app/core/config.py
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

# Absolute paths so settings load the same way no matter which directory
# uvicorn or pytest was started from. Later entries win on conflicts.
ENV_FILES = (REPO_ROOT / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Typed settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FlyCompare AI"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://flycompare:change-me-local-only@localhost:5432/flycompare"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )
    jwt_secret_key: str = "development-only-change-this-secret"
    jwt_access_token_expire_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
