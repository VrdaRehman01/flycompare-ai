"""Settings used when the app runs on hosting providers."""

import httpx
import pytest

from app.core.config import get_settings
from app.core.database import normalise_database_url
from app.services import email_service


@pytest.mark.parametrize("raw,expected", [
    ("postgres://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("sqlite:///./flycompare.db", "sqlite:///./flycompare.db"),
])
def test_database_urls_from_hosting_providers_are_accepted(raw, expected):
    assert normalise_database_url(raw) == expected


class _Recorder:
    sent: list = []
    status = 201

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):
        _Recorder.sent.append((url, json, headers))
        return httpx.Response(_Recorder.status)


def test_brevo_sends_over_https_and_reports_refusals(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "brevo")
    monkeypatch.setattr(settings, "brevo_api_key", "key-123")
    monkeypatch.setattr(settings, "email_from", "me@gmail.com")
    monkeypatch.setattr(email_service.httpx, "Client", _Recorder)
    _Recorder.sent.clear()

    email_service._send_brevo("you@example.com", "Hi", "text body", "<p>html</p>")
    url, payload, headers = _Recorder.sent[-1]
    assert url == email_service.BREVO_URL and headers["api-key"] == "key-123"
    assert payload["sender"]["email"] == "me@gmail.com" and payload["to"] == [{"email": "you@example.com"}]
    assert payload["textContent"] == "text body" and payload["htmlContent"] == "<p>html</p>"

    _Recorder.status = 401
    with pytest.raises(email_service.EmailDeliveryFailed):
        email_service._send_brevo("you@example.com", "Hi", "text")
    _Recorder.status = 201
