"""Security controls added in the pre-deployment review."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.providers.travelpayouts_provider import TravelpayoutsFlightProvider
from app.schemas.flight import FlightSearchRequest
from tests.conftest import future

SEARCH = {"origin": "KHI", "destination": "DXB", "departure_date": future(20), "trip_type": "one-way", "passengers": 1, "cabin": "Economy"}


def test_every_response_carries_security_headers(client):
    headers = client.get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "strict-transport-security" not in headers  # HSTS only outside development


def test_oversized_request_bodies_are_refused(client):
    huge = {"offer": {"id": "off_x", "airline": "X", "price": 1, "currency": "USD", "origin": "KHI", "destination": "DXB", "pad": "x" * 600_000}}
    response = client.post("/api/account/saved-flights", json=huge)
    assert response.status_code == 413


def test_state_changing_public_routes_require_the_csrf_header():
    bare = TestClient(app)
    assert bare.post("/api/flights/search", json=SEARCH).status_code == 403
    assert bare.post("/api/planner/plan", json={"location": "DXB", "start": future(10), "end": future(12)}).status_code == 403


def test_provider_diagnostics_exist_only_in_development(client, monkeypatch):
    assert client.get("/api/flights/provider").status_code == 200
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert client.get("/api/flights/provider").status_code == 404


def test_global_search_ceiling_applies_across_visitors(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_search_per_minute", 100)
    monkeypatch.setattr(get_settings(), "rate_limit_search_global_per_minute", 2)
    assert client.post("/api/flights/search", json=SEARCH).status_code == 200
    assert client.post("/api/flights/search", json=SEARCH).status_code == 200
    assert client.post("/api/flights/search", json=SEARCH).status_code == 429


@pytest.mark.parametrize("link,allowed", [
    ("/search/LHE0312DXB1?t=abc", True),
    ("//evil.example/x", False),
    ("@evil.example/x", False),
    ("/\\evil.example", False),
    ("https://evil.example/", False),
])
def test_booking_links_only_point_at_the_booking_site(link, allowed, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "travelpayouts_token", "tok")
    provider = TravelpayoutsFlightProvider(settings)
    monkeypatch.setattr(provider, "_airline_name", lambda code: code)
    request = FlightSearchRequest(origin="LHE", destination="DXB", departure_date=future(30), trip_type="one-way")
    fare = {"departure_at": f"{future(30)}T13:40:00+05:00", "price": 200, "airline": "PK", "flight_number": "203", "duration_to": 230, "link": link}
    offer = provider._map(fare, request, 1, None or __import__("datetime").datetime.now())
    assert (offer.booking_url is not None) == allowed
    if allowed:
        assert offer.booking_url.startswith("https://www.aviasales.com/search/")


def test_production_hides_api_docs_and_debug():
    """Import the app in a fresh process configured as production (docs are fixed at start-up)."""
    env = {**os.environ, "APP_ENV": "production", "APP_DEBUG": "true", "SECRET_KEY": "x" * 40, "FLIGHT_PROVIDER": "mock"}
    code = (
        "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app);"
        "print(app.debug, c.get('/docs').status_code, c.get('/openapi.json').status_code, 'docs' in c.get('/').json(),"
        " c.get('/health').headers.get('strict-transport-security') is not None)"
    )
    backend = Path(__file__).resolve().parents[1]
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, env=env, capture_output=True, text=True, timeout=120, check=True)  # nosec B603
    assert out.stdout.split() == ["False", "404", "404", "False", "True"]
