"""Sign-in and verification by emailed one-time codes."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.models import EmailCode, User
from app.services import email_service
from tests.conftest import OUTBOX, last_code, make_client, register

EMAIL = "traveller@example.com"


def _request(c, email=EMAIL):
    return c.post("/api/auth/code/request", json={"email": email})


def _verify(c, code, email=EMAIL, **extra):
    return c.post("/api/auth/code/verify", json={"email": email, "code": code, **extra})


def test_code_sign_in_creates_a_verified_passwordless_account(client, db_session):
    sent = _request(client)
    assert sent.status_code == 202
    assert sent.json() == {"verification_required": True, "email": EMAIL, "expires_in_seconds": 600, "resend_after_seconds": 60}
    assert OUTBOX[-1]["to"] == EMAIL and "sign in" in OUTBOX[-1]["text"]

    user = _verify(client, last_code(EMAIL), name="Sana").json()
    assert user["email"] == EMAIL and user["name"] == "Sana"
    assert user["email_verified"] is True and user["has_password"] is False
    assert client.get("/api/auth/me").json()["id"] == user["id"]


def test_codes_are_stored_only_as_hashes(client, db_session):
    _request(client)
    code = last_code(EMAIL)
    row = db_session.scalar(select(EmailCode))
    assert code not in row.code_hash and len(row.code_hash) == 64


def test_wrong_codes_count_down_then_retire_the_code(client):
    _request(client)
    code = last_code(EMAIL)
    wrong = "000000" if code != "000000" else "111111"
    first = _verify(client, wrong)
    assert first.status_code == 400 and "4 attempts left" in first.json()["detail"]
    for _ in range(4):
        last = _verify(client, wrong)
    assert "Too many incorrect attempts" in last.json()["detail"]
    # Even the right code no longer works once the attempts are used up.
    assert _verify(client, code).status_code == 400
    assert client.get("/api/auth/me").json() is None


def test_codes_work_once_and_expire(client, db_session):
    _request(client)
    code = last_code(EMAIL)
    assert _verify(client, code).status_code == 200
    reused = _verify(make_client(), code)
    assert reused.status_code == 400 and "no longer valid" in reused.json()["detail"]

    other = "late@example.com"
    _request(client, other)
    row = db_session.scalar(select(EmailCode).where(EmailCode.email == other))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    expired = _verify(make_client(), last_code(other), email=other)
    assert expired.status_code == 400 and "expired" in expired.json()["detail"]


def test_a_new_code_replaces_the_previous_one(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_code_resend_seconds", 0)
    _request(client)
    first = last_code(EMAIL)
    _request(client)
    second = last_code(EMAIL)
    if first != second:
        assert _verify(client, first).status_code == 400
    assert _verify(client, second).status_code == 200


def test_resend_cooldown_and_hourly_cap(client, monkeypatch):
    assert _request(client).status_code == 202
    again = _request(client)
    assert again.status_code == 429 and "Retry-After" in again.headers

    monkeypatch.setattr(get_settings(), "login_code_resend_seconds", 0)
    monkeypatch.setattr(get_settings(), "login_codes_per_hour", 3)
    assert _request(client).status_code == 202
    assert _request(client).status_code == 202
    capped = _request(client)
    assert capped.status_code == 429 and "Too many codes" in capped.json()["detail"]


def test_responses_do_not_reveal_whether_an_account_exists(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_code_resend_seconds", 0)
    register(client)
    existing = _request(make_client(), "ayesha@example.com")
    unknown = _request(make_client(), "nobody@example.com")
    assert existing.status_code == unknown.status_code == 202
    assert existing.json().keys() == unknown.json().keys()


def test_email_problems_are_reported_not_hidden(client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    off = _request(client)
    assert off.status_code == 503 and "not available" in off.json()["detail"]

    monkeypatch.setattr(email_service, "is_configured", lambda: True)

    def fail(*args, **kwargs):
        raise email_service.EmailDeliveryFailed("smtp down")

    monkeypatch.setattr(email_service, "send", fail)
    failed = _request(client, "x@example.com")
    assert failed.status_code == 502 and "couldn't send" in failed.json()["detail"]


def test_unverified_password_accounts_confirm_by_code_once(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_code_resend_seconds", 0)
    register(client)
    client.post("/api/auth/logout")
    user = db_session.scalar(select(User))
    user.email_verified_at = None  # e.g. an account created before verification existed
    db_session.commit()

    pending = client.post("/api/auth/login", json={"email": "ayesha@example.com", "password": "secret123"})
    assert pending.status_code == 202 and pending.json()["verification_required"] is True
    assert client.get("/api/auth/me").json() is None
    verified = _verify(client, last_code("ayesha@example.com"), email="ayesha@example.com")
    assert verified.status_code == 200 and verified.json()["email_verified"] is True

    client.post("/api/auth/logout")
    direct = client.post("/api/auth/login", json={"email": "ayesha@example.com", "password": "secret123"})
    assert direct.status_code == 200 and direct.json()["email_verified"] is True


def test_wrong_password_never_sends_a_code(client):
    register(client)
    sent_before = len(OUTBOX)
    assert make_client().post("/api/auth/login", json={"email": "ayesha@example.com", "password": "wrong-pass1"}).status_code == 401
    assert len(OUTBOX) == sent_before


def test_passwordless_accounts_can_set_a_password_and_delete_without_one(client):
    _request(client)
    _verify(client, last_code(EMAIL))
    assert client.post("/api/account/password", json={"new_password": "brandnew1"}).status_code == 204
    assert client.get("/api/auth/me").json()["has_password"] is True
    assert make_client().post("/api/auth/login", json={"email": EMAIL, "password": "brandnew1"}).status_code == 200

    other = make_client()
    _request(other, "solo@example.com")
    _verify(other, last_code("solo@example.com"), email="solo@example.com")
    assert other.post("/api/account/delete", json={"confirm": "DELETE"}).status_code == 204
    assert other.get("/api/auth/me").json() is None


def test_changing_email_requires_verifying_the_new_address(client):
    register(client)
    changed = client.patch("/api/account/profile", json={"email": "new@example.com", "current_password": "secret123"})
    assert changed.status_code == 200 and changed.json()["email_verified"] is False
