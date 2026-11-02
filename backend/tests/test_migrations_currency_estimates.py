from datetime import date

import httpx
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.core.database import init_db
from app.services import currency_service, prediction_service


def test_migration_upgrades_existing_history_without_losing_rows():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE flight_search_history (id INTEGER PRIMARY KEY, origin VARCHAR(100) NOT NULL, destination VARCHAR(100) NOT NULL,"
            " departure_date DATE NOT NULL, return_date DATE, trip_type VARCHAR(20) NOT NULL, passengers INTEGER NOT NULL,"
            " cabin VARCHAR(30) NOT NULL, result_count INTEGER NOT NULL, created_at DATETIME NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO flight_search_history VALUES (1,'Karachi (KHI)','Dubai (DXB)','2026-11-15',NULL,'one-way',1,'Economy',3,'2026-10-17 02:53:57'),"
            " (2,'KHI','Japan','2026-11-15',NULL,'one-way',1,'Economy',0,'2026-10-18 02:53:57')"
        ))

    init_db(engine)
    init_db(engine)  # idempotent

    columns = {c["name"] for c in inspect(engine).get_columns("flight_search_history")}
    assert {"user_id", "origin_code", "destination_code", "currency", "min_price", "children", "infants", "legs"} <= columns
    assert "connections" in {c["name"] for c in inspect(engine).get_columns("fare_observations")}
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, origin_code, destination_code, user_id FROM flight_search_history ORDER BY id")).all()
        versions = conn.execute(text("SELECT version FROM schema_migrations")).scalars().all()
    assert rows == [(1, "KHI", "DXB", None), (2, "KHI", None, None)]
    assert versions == ["0001_search_history_context", "0002_passengers_multicity_connections", "0003_destination_image_sources", "0004_observation_airline_identity", "0005_email_verification"]
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()


class _FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("GET", "http://x"), response=httpx.Response(self.status_code))


class _FakeClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        _FakeClient.calls += 1
        if params["base"] == "PKR":
            return _FakeResponse(404, {"message": "not found"})
        return _FakeResponse(200, {"base": params["base"], "date": "2026-10-30", "rates": {"EUR": 0.9, "GBP": 0.75}})


def test_currency_rates_are_fetched_cached_and_unsupported_currencies_reported(client, monkeypatch):
    monkeypatch.setattr(currency_service.httpx, "Client", _FakeClient)
    _FakeClient.calls = 0
    first = client.get("/api/currency/rates?base=USD").json()
    assert first["rates"]["EUR"] == 0.9
    assert "European Central Bank" in first["source"]
    client.get("/api/currency/rates?base=USD")
    assert _FakeClient.calls == 1  # cached

    unsupported = client.get("/api/currency/rates?base=PKR")
    assert unsupported.status_code == 503
    assert client.get("/api/currency/rates?base=usd").status_code == 422


class _FallbackClient(_FakeClient):
    def get(self, url, params=None):
        if "fallback" in url:
            base = url.rsplit("/", 1)[-1]
            return _FakeResponse(200, {"result": "success", "base_code": base, "time_last_update_utc": "Fri, 30 Oct 2026",
                                       "rates": {base: 1, "EUR": 0.5, "PKR": 280.0}})
        return super().get(url, params)


def test_fallback_fills_currencies_ecb_does_not_publish(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "currency_fallback_api_url", "http://fallback.test/v6/latest")
    monkeypatch.setattr(currency_service.httpx, "Client", _FallbackClient)
    usd = client.get("/api/currency/rates?base=USD").json()
    assert usd["rates"]["EUR"] == 0.9  # ECB wins where both publish
    assert usd["rates"]["PKR"] == 280.0  # filled in by the fallback
    assert "European Central Bank" in usd["source"] and "ExchangeRate-API" in usd["source"]

    pkr = client.get("/api/currency/rates?base=PKR")  # not an ECB base, so fallback only
    assert pkr.status_code == 200
    assert pkr.json()["source"] == currency_service.FALLBACK_SOURCE
    assert "PKR" not in pkr.json()["rates"]


def test_currency_unavailable_when_network_fails(client):
    # The test configuration points at an unreachable host.
    response = client.get("/api/currency/rates?base=USD")
    assert response.status_code == 503


def _model_available() -> bool:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        return False
    from app.core.config import REPO_ROOT, get_settings

    return (REPO_ROOT / get_settings().fare_model_path).is_file()


@pytest.mark.skipif(not _model_available(), reason="ML stack or model artifact not installed")
def test_fare_estimate_only_within_model_coverage():
    ok = prediction_service.estimate("KHI", "DXB", date(2026, 12, 10))
    assert ok["available"] is True
    assert ok["currency"] == "EUR" and ok["estimate"] > 0
    assert "not a live" in ok["label"]

    outside = prediction_service.estimate("KHI", "DXB", date(2028, 6, 1))
    assert outside["available"] is False and "only covers" in outside["reason"]

    unknown = prediction_service.estimate("LHE", "XXX", date(2026, 12, 10))
    assert unknown["available"] is False


def test_fare_estimate_endpoint_validates_codes(client):
    assert client.get("/api/prices/estimate?origin=karachi&destination=DXB&departure_date=2026-12-10").status_code == 422
    response = client.get("/api/prices/estimate?origin=KHI&destination=DXB&departure_date=2026-12-10")
    assert response.status_code == 200 and "available" in response.json()
