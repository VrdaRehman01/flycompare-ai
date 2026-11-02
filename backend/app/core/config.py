
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

ENV_FILES = (REPO_ROOT / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FlyCompare AI"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api"

    # SQLite needs no setup for local development; use PostgreSQL in production, e.g.
    # postgresql+psycopg://user:password@host:5432/flycompare
    database_url: str = "sqlite:///./flycompare.db"

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    # "mock" (simulated demo offers, development only) or "duffel". Outside development
    # only providers returning live data are allowed; see build_flight_provider.
    flight_provider: str = "mock"
    duffel_access_token: str | None = None
    duffel_api_url: str = "https://api.duffel.com"
    duffel_api_version: str = "v2"
    duffel_timeout_seconds: float = 45.0
    # Accommodation: "auto" uses Duffel Stays when FLIGHT_PROVIDER=duffel (falling back to
    # demo stays if Stays is not enabled on the account), "duffel" always tries it, "demo" never does.
    stays_provider: str = "auto"
    # Stays, cars, transfers, tours and flight + hotel have no real inventory provider yet
    # and would show simulated options, so they are hidden unless explicitly enabled.
    demo_travel_services_enabled: bool = False
    # Travel guides and the trip planner fetch Wikipedia summaries and Open-Meteo
    # climate history. Disable to run fully offline (tests do).
    travel_external_data_enabled: bool = True

    # Browser sessions are opaque random tokens stored hashed in the database
    # and sent to the browser only as an HttpOnly cookie.
    session_cookie_name: str = "fc_session"
    session_ttl_hours: int = 24 * 7
    session_cookie_secure: bool | None = None  # None = secure outside development

    # Simple per-client request limits (requests per minute).
    rate_limit_auth_per_minute: int = 10
    rate_limit_search_per_minute: int = 20
    rate_limit_enabled: bool = True

    # Exchange rates: European Central Bank reference rates via Frankfurter.
    currency_api_url: str = "https://api.frankfurter.dev/v1"
    # ECB publishes ~30 currencies (no PKR, AED, SAR...). This free, keyless source
    # fills in the rest; ECB rates win wherever both publish. Empty disables it.
    currency_fallback_api_url: str = "https://open.er-api.com/v6/latest"
    currency_cache_seconds: int = 6 * 60 * 60
    currency_timeout_seconds: float = 8.0

    # Destination photos (Wikipedia / Wikimedia Commons). Wikimedia refuses (HTTP 403)
    # clients that do not identify themselves with contact details (URL or email),
    # so set WIKIMEDIA_USER_AGENT to include your site URL or a contact address.
    destination_images_enabled: bool = True
    wikimedia_user_agent: str = "FlyCompareAI/0.3 (self-hosted travel comparison; destination photos)"

    # Optional ML fare estimate artifact (relative to the repository root).
    fare_model_path: str = "ml/models/fare_log_ridge_model.joblib"

    @property
    def is_development(self) -> bool:
        """Local development or automated tests; anything else is treated as production."""
        return self.app_env.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def secure_cookies(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return not self.is_development


@lru_cache
def get_settings() -> Settings:
    return Settings()
