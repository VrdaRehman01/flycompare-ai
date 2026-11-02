"""Rules that keep simulated or sandbox data away from real users."""

import pytest

from app.core.config import get_settings
from app.providers.factory import ProviderConfigError, build_flight_provider
from tests.conftest import future


def test_mock_provider_is_allowed_in_development_only(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "flight_provider", "mock")
    assert build_flight_provider(settings)[1] == "demo"
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(ProviderConfigError, match="no live flight data provider"):
        build_flight_provider(settings)


def test_duffel_sandbox_token_is_refused_in_production(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "flight_provider", "duffel")
    monkeypatch.setattr(settings, "duffel_access_token", "duffel_test_abc")
    assert build_flight_provider(settings)[1] == "test"
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(ProviderConfigError):
        build_flight_provider(settings)
    monkeypatch.setattr(settings, "duffel_access_token", "duffel_live_abc")
    assert build_flight_provider(settings)[1] == "live"


def test_search_reports_unavailable_instead_of_simulating_in_production(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "flight_provider", "mock")
    monkeypatch.setattr(settings, "app_env", "production")
    body = {"origin": "KHI", "destination": "DXB", "departure_date": future(20), "trip_type": "one-way", "passengers": 1, "cabin": "Economy"}
    response = client.post("/api/flights/search", json=body)
    assert response.status_code == 503
    assert "not available" in response.json()["detail"]


def test_simulated_travel_services_are_hidden_unless_enabled(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_travel_services_enabled", False)
    features = client.get("/api/meta").json()["features"]
    assert "stays" not in features and "packages" not in features and "guides" in features
    params = {"location": "DXB", "check_in": future(10), "check_out": future(12)}
    assert client.get("/api/stays/search", params=params).status_code == 404
    assert client.get("/api/tours/search", params={"location": "DXB", "date": future(10)}).status_code == 404
    assert client.get("/api/guides").status_code == 200  # built on real data, stays available

    monkeypatch.setattr(settings, "demo_travel_services_enabled", True)
    assert "stays" in client.get("/api/meta").json()["features"]
    assert client.get("/api/stays/search", params=params).status_code == 200
