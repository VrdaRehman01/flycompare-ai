"""Price alerts: management, the checking rules and the scheduler endpoint."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import PriceAlert
from app.providers.errors import FlightProviderError
from app.services import alert_service
from tests.conftest import OUTBOX, future, make_client, register

TRIP = {"origin": "LHE", "destination": "DXB", "departure_date": future(30), "return_date": future(37), "target_price": 450}


class FakeProvider:
    def __init__(self, *prices, fail=False):
        self.prices, self.fail, self.calls = list(prices), fail, 0

    def search(self, request):
        self.calls += 1
        if self.fail:
            raise FlightProviderError("The fare source is busy right now.")
        price = self.prices.pop(0) if self.prices else None
        return [] if price is None else [SimpleNamespace(price=price, currency="USD", booking_url="https://www.aviasales.com/search/x?marker=1")]


def _alert(db):
    return db.scalar(select(PriceAlert))


def test_alerts_need_a_verified_account_and_stay_private(client):
    assert client.post("/api/account/alerts", json=TRIP).status_code == 401
    register(client)
    created = client.post("/api/account/alerts", json=TRIP)
    assert created.status_code == 201 and created.json()["target_price"] == 450 and created.json()["active"]

    other = make_client()
    register(other, email="other@example.com")
    assert other.get("/api/account/alerts").json() == []
    assert other.delete(f"/api/account/alerts/{created.json()['id']}").status_code == 404
    assert client.delete(f"/api/account/alerts/{created.json()['id']}").status_code == 204
    assert client.get("/api/account/alerts").json() == []


def test_alert_validation_duplicates_and_limit(client, monkeypatch):
    register(client)
    assert client.post("/api/account/alerts", json={**TRIP, "destination": "LHE"}).status_code == 422
    assert client.post("/api/account/alerts", json={**TRIP, "target_price": 0}).status_code == 422
    assert client.post("/api/account/alerts", json={**TRIP, "departure_date": (date.today() - timedelta(days=1)).isoformat(), "return_date": None}).status_code == 422
    first = client.post("/api/account/alerts", json=TRIP).json()
    again = client.post("/api/account/alerts", json={**TRIP, "target_price": 400}).json()
    assert again["id"] == first["id"] and again["target_price"] == 400  # same trip updates the target
    monkeypatch.setattr(get_settings(), "alerts_per_user", 1)
    assert client.post("/api/account/alerts", json={**TRIP, "destination": "IST"}).status_code == 409


def test_email_goes_out_once_per_new_low_at_or_below_target(client, db_session):
    register(client)
    client.post("/api/account/alerts", json=TRIP)
    alert = _alert(db_session)
    provider = FakeProvider(480, 440, 445, 430)

    assert alert_service.check_alert(db_session, alert, provider) == "checked"  # above target
    assert alert.last_price == 480 and not OUTBOX[1:]
    assert alert_service.check_alert(db_session, alert, provider) == "notified"
    mail = OUTBOX[-1]
    assert mail["to"] == "ayesha@example.com" and "USD 440" in mail["subject"] and "marker=1" in mail["text"]
    assert alert_service.check_alert(db_session, alert, provider) == "checked"  # 445: below target but not a new low
    assert alert_service.check_alert(db_session, alert, provider) == "notified"  # 430: a new low
    assert alert.notified_price == 430


def test_failures_are_recorded_not_notified(client, db_session, monkeypatch):
    register(client)
    client.post("/api/account/alerts", json=TRIP)
    alert = _alert(db_session)
    sent = len(OUTBOX)
    assert alert_service.check_alert(db_session, alert, FakeProvider(fail=True)) == "error"
    assert "busy" in alert.last_error and len(OUTBOX) == sent

    from app.services import email_service

    def down(*a, **k):
        raise email_service.EmailDeliveryFailed("smtp down")

    monkeypatch.setattr(email_service, "send", down)
    assert alert_service.check_alert(db_session, alert, FakeProvider(400)) == "error"
    assert alert.notified_price is None and "could not be sent" in alert.last_error


def test_past_trips_are_switched_off(client, db_session):
    register(client)
    client.post("/api/account/alerts", json=TRIP)
    alert = _alert(db_session)
    alert.departure_date = date.today() - timedelta(days=1)
    db_session.commit()
    provider = FakeProvider(100)
    assert alert_service.check_alert(db_session, alert, provider) == "expired"
    assert not alert.active and provider.calls == 0


def test_run_due_respects_the_recheck_window(client, db_session, monkeypatch):
    register(client)
    client.post("/api/account/alerts", json=TRIP)
    provider = FakeProvider(500, 500)
    monkeypatch.setattr(alert_service, "build_flight_provider", lambda settings: (provider, "recent"))
    assert alert_service.run_due(db_session)["checked"] == 1
    assert alert_service.run_due(db_session)["checked"] == 0  # checked moments ago
    assert provider.calls == 1


@pytest.mark.parametrize("token,header,status", [("", "Bearer anything", 404), ("s3cret", "Bearer wrong", 404), ("s3cret", "Bearer s3cret", 200)])
def test_scheduler_endpoint_requires_the_cron_token(client, monkeypatch, token, header, status):
    monkeypatch.setattr(get_settings(), "alerts_cron_token", token)
    monkeypatch.setattr(alert_service, "build_flight_provider", lambda settings: (FakeProvider(), "recent"))
    response = client.post("/api/internal/alerts/run", headers={"Authorization": header})
    assert response.status_code == status
    if status == 200:
        assert set(response.json()) >= {"notified", "checked", "expired", "error"}


def test_deleting_the_account_removes_alerts(client, db_session):
    register(client)
    client.post("/api/account/alerts", json=TRIP)
    assert client.post("/api/account/delete", json={"password": "secret123", "confirm": "DELETE"}).status_code == 204
    assert db_session.scalar(select(PriceAlert)) is None
