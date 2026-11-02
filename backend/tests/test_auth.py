from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import SavedFlight, User, UserSession
from tests.conftest import OUTBOX, last_code, make_client, register


def test_password_hashing_is_salted_and_verifiable():
    first, second = hash_password("secret123"), hash_password("secret123")
    assert first != second
    assert "secret123" not in first
    assert verify_password("secret123", first)
    assert not verify_password("wrong-pass1", first)
    assert not verify_password("secret123", "garbage")


def test_register_sets_httponly_session_and_never_stores_plaintext(client, db_session):
    user = register(client)
    assert user["email"] == "ayesha@example.com"
    assert "password" not in user and "password_hash" not in user

    cookie_header = client.cookies.jar
    assert any(c.name == get_settings().session_cookie_name for c in cookie_header)

    stored = db_session.scalar(select(User))
    assert stored.password_hash.startswith("scrypt$")
    assert "secret123" not in stored.password_hash
    # Only a hash of the session token is stored.
    token = client.cookies.get(get_settings().session_cookie_name)
    assert db_session.scalar(select(UserSession.token_hash)) != token

    me = client.get("/api/auth/me").json()
    assert me["id"] == user["id"]


def test_register_sets_cookie_flags_only_after_email_verification(client):
    pending = client.post("/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "secret123"})
    assert pending.status_code == 202 and "set-cookie" not in pending.headers
    response = client.post("/api/auth/code/verify", json={"email": "a@example.com", "code": last_code("a@example.com")})
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


def test_register_validation_and_duplicates(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_code_resend_seconds", 0)
    assert client.post("/api/auth/register", json={"name": "A", "email": "not-an-email", "password": "secret123"}).status_code == 422
    assert client.post("/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "short1"}).status_code == 422
    assert client.post("/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "lettersonly"}).status_code == 422
    register(client, email="a@example.com")
    original_hash = db_session.scalar(select(User.password_hash))
    # Registering an existing address looks exactly like a new registration (no enumeration)...
    duplicate = make_client().post("/api/auth/register", json={"name": "B", "email": "A@Example.com", "password": "other-pass9"})
    assert duplicate.status_code == 202
    assert "already have one" in OUTBOX[-1]["text"]
    # ...and confirming it signs the owner in without replacing their password.
    intruder = make_client()
    assert intruder.post("/api/auth/code/verify", json={"email": "a@example.com", "code": last_code("a@example.com")}).status_code == 200
    db_session.expire_all()
    assert db_session.scalar(select(User.password_hash)) == original_hash


def test_login_logout_flow(client):
    register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json() is None

    bad = client.post("/api/auth/login", json={"email": "ayesha@example.com", "password": "wrong-pass1"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "secret123"})
    assert unknown.status_code == 401
    assert bad.json()["detail"] == unknown.json()["detail"]  # does not reveal which emails exist

    ok = client.post("/api/auth/login", json={"email": "AYESHA@example.com", "password": "secret123"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "ayesha@example.com"


def test_logout_invalidates_the_server_session(client):
    register(client)
    token = client.cookies.get(get_settings().session_cookie_name)
    client.post("/api/auth/logout")
    other = make_client()
    other.cookies.set(get_settings().session_cookie_name, token)
    assert other.get("/api/auth/me").json() is None
    assert other.get("/api/account/profile").status_code == 401


def test_state_changing_requests_require_csrf_header(client):
    from fastapi.testclient import TestClient

    from app.main import app

    bare = TestClient(app)
    response = bare.post("/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "secret123"})
    assert response.status_code == 403


def test_profile_update_and_email_change_requires_password(client):
    register(client)
    renamed = client.patch("/api/account/profile", json={"name": "  Ayesha   K  "})
    assert renamed.json()["name"] == "Ayesha K"

    no_password = client.patch("/api/account/profile", json={"email": "new@example.com"})
    assert no_password.status_code == 400
    changed = client.patch("/api/account/profile", json={"email": "new@example.com", "current_password": "secret123"})
    assert changed.status_code == 200 and changed.json()["email"] == "new@example.com"


def test_change_password_signs_out_other_sessions(client):
    register(client)
    other_device = make_client()
    assert other_device.post("/api/auth/login", json={"email": "ayesha@example.com", "password": "secret123"}).status_code == 200

    assert client.post("/api/account/password", json={"current_password": "wrong-pass1", "new_password": "newsecret1"}).status_code == 400
    assert client.post("/api/account/password", json={"current_password": "secret123", "new_password": "newsecret1"}).status_code == 204

    assert client.get("/api/auth/me").json() is not None  # current session kept
    assert other_device.get("/api/auth/me").json() is None
    assert make_client().post("/api/auth/login", json={"email": "ayesha@example.com", "password": "newsecret1"}).status_code == 200


def test_preferences_are_validated_and_saved(client):
    register(client)
    saved = client.put("/api/account/preferences", json={"home_airport": "KHI", "cabin": "Business", "passengers": 2, "currency": "EUR", "theme": "dark"})
    assert saved.status_code == 200
    assert saved.json()["preferences"]["home_airport"] == "KHI"
    assert client.put("/api/account/preferences", json={"home_airport": "karachi"}).status_code == 422
    assert client.get("/api/account/profile").json()["preferences"]["theme"] == "dark"


def test_delete_account_requires_confirmation_and_removes_data(client, db_session):
    register(client)
    client.post("/api/account/saved-flights", json={"offer": {"id": "off_1", "airline": "X", "price": 1, "currency": "USD", "origin": "KHI", "destination": "DXB"}})
    assert client.post("/api/account/delete", json={"password": "secret123", "confirm": "yes"}).status_code == 422
    assert client.post("/api/account/delete", json={"password": "wrong-pass1", "confirm": "DELETE"}).status_code == 400
    assert client.post("/api/account/delete", json={"password": "secret123", "confirm": "DELETE"}).status_code == 204

    assert db_session.scalar(select(User)) is None
    assert db_session.scalar(select(SavedFlight)) is None
    assert db_session.scalar(select(UserSession)) is None
    assert client.get("/api/auth/me").json() is None


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_minute", 3)
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "secret123"})
    limited = client.post("/api/auth/login", json={"email": "x@example.com", "password": "secret123"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
