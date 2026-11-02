
import os

# Tests must never depend on live services or a developer's local .env choices.
# Environment variables take precedence over values in .env files.
os.environ["FLIGHT_PROVIDER"] = "mock"
os.environ["DUFFEL_ACCESS_TOKEN"] = ""
os.environ["APP_ENV"] = "test"
os.environ["CURRENCY_API_URL"] = "http://currency.invalid/v1"
os.environ["CURRENCY_FALLBACK_API_URL"] = ""
os.environ["STAYS_PROVIDER"] = "demo"
# The simulated travel services are off by default; their tests exercise the logic directly.
os.environ["DEMO_TRAVEL_SERVICES_ENABLED"] = "true"
os.environ["TRAVEL_EXTERNAL_DATA_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db, init_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.services import currency_service  # noqa: E402

get_settings.cache_clear()

CSRF = {"X-Requested-With": "FlyCompare"}


def future(days: int) -> str:
    """ISO date relative to today, so tests never go stale."""
    from datetime import date, timedelta

    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def use_test_database():
    """Give each test an isolated in-memory SQLite database (with migrations applied)."""
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    currency_service.clear_cache()
    try:
        yield TestSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()


@pytest.fixture
def db_session(use_test_database):
    with use_test_database() as session:
        yield session


@pytest.fixture
def client():
    # Not used as a context manager: that would run the app lifespan, which
    # initialises the real configured database instead of the test one.
    return TestClient(app, headers=CSRF)


def make_client() -> TestClient:
    """A separate browser (own cookie jar) for multi-user tests."""
    return TestClient(app, headers=CSRF)


def register(c: TestClient, email: str = "ayesha@example.com", password: str = "secret123", name: str = "Ayesha Khan"):
    response = c.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()
