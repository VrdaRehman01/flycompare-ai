"""One-time codes sent by email, for passwordless sign-in and for verifying new accounts.

Rules:
- Six random digits from ``secrets``; only HMAC-SHA256(secret_key, email:code) is stored,
  so a database leak does not reveal usable codes.
- A code expires after ``login_code_ttl_minutes`` and works once. Requesting a new code
  retires the previous one, so only the newest code for an address is ever valid.
- Wrong guesses are counted; after ``login_code_max_attempts`` the code is retired.
- Sending is limited per address (one per ``login_code_resend_seconds`` and
  ``login_codes_per_hour``) on top of the per-IP limit on the auth routes.
- Responses never depend on whether an account exists for the address.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmailCode, User
from app.services import email_service

PURPOSES = ("login", "register")
UNUSABLE_PASSWORD = "!"  # stored for accounts created by code sign-in; never verifies


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(email: str, code: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _email_body(code: str, purpose: str, has_account: bool) -> tuple[str, str, str]:
    minutes = get_settings().login_code_ttl_minutes
    if purpose == "register" and has_account:
        intro = "Someone (hopefully you) tried to create a FlyCompare AI account with this email, but you already have one. Use this code to sign in instead:"
    elif purpose == "register":
        intro = "Use this code to confirm your email and finish creating your FlyCompare AI account:"
    else:
        intro = "Use this code to sign in to FlyCompare AI:"
    subject = f"{code} is your FlyCompare AI code"
    text = f"{intro}\n\n    {code}\n\nIt expires in {minutes} minutes and can be used once.\nIf you didn't ask for this, you can ignore this email; nobody can sign in without the code."
    html = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;color:#172844\">"
        "<h2 style=\"margin:0 0 12px;font-size:20px\">FlyCompare <span style=\"color:#1a6dff\">AI</span></h2>"
        f"<p style=\"font-size:15px;line-height:1.5\">{intro}</p>"
        f"<p style=\"font-size:32px;font-weight:700;letter-spacing:8px;margin:20px 0;padding:14px 18px;background:#eef3fe;border-radius:12px;text-align:center\">{code}</p>"
        f"<p style=\"font-size:13px;color:#64748b\">It expires in {minutes} minutes and can be used once. "
        "If you didn't ask for this, you can ignore this email; nobody can sign in without the code.</p></div>"
    )
    return subject, text, html


def issue(db: Session, email: str, purpose: str, payload: dict | None = None) -> dict:
    """Create and email a new code for ``email``. Raises HTTPException on limits or delivery failure."""
    settings = get_settings()
    if purpose not in PURPOSES:
        raise ValueError(purpose)
    if not email_service.is_configured():
        raise HTTPException(status_code=503, detail="Sign-in by email code is not available right now.")
    now = _now()
    latest = db.scalar(select(EmailCode).where(EmailCode.email == email).order_by(EmailCode.created_at.desc()).limit(1))
    if latest is not None:
        wait = settings.login_code_resend_seconds - (now - _aware(latest.created_at)).total_seconds()
        if wait > 0:
            raise HTTPException(status_code=429, detail=f"Please wait {int(wait) + 1} seconds before requesting another code.",
                                headers={"Retry-After": str(int(wait) + 1)})
    sent_last_hour = db.scalar(select(func.count(EmailCode.id)).where(EmailCode.email == email, EmailCode.created_at > now - timedelta(hours=1)))
    if sent_last_hour >= settings.login_codes_per_hour:
        raise HTTPException(status_code=429, detail="Too many codes requested for this email. Please try again later.", headers={"Retry-After": "900"})

    code = f"{secrets.randbelow(10**6):06d}"
    has_account = db.scalar(select(User.id).where(User.email == email)) is not None
    subject, text, html = _email_body(code, purpose, has_account)
    try:
        email_service.send(email, subject, text, html)
    except email_service.EmailNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Sign-in by email code is not available right now.") from exc
    except email_service.EmailDeliveryFailed as exc:
        raise HTTPException(status_code=502, detail="We couldn't send the email. Check the address and try again in a moment.") from exc

    # Only the newest code is valid: retire earlier unused ones.
    db.execute(update(EmailCode).where(EmailCode.email == email, EmailCode.consumed_at.is_(None)).values(consumed_at=now))
    db.add(EmailCode(email=email, purpose=purpose, code_hash=_hash(email, code), payload=payload,
                     created_at=now, expires_at=now + timedelta(minutes=settings.login_code_ttl_minutes)))
    db.commit()
    return {"email": email, "expires_in_seconds": settings.login_code_ttl_minutes * 60, "resend_after_seconds": settings.login_code_resend_seconds}


def verify(db: Session, email: str, code: str) -> EmailCode:
    """Check ``code`` against the newest code for ``email``; on success mark it used and return it."""
    settings = get_settings()
    now = _now()
    row = db.scalar(select(EmailCode).where(EmailCode.email == email).order_by(EmailCode.created_at.desc()).limit(1))
    if row is None or row.consumed_at is not None:
        raise HTTPException(status_code=400, detail="This code is no longer valid. Request a new code.")
    if _aware(row.expires_at) <= now:
        row.consumed_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="This code has expired. Request a new code.")
    if not hmac.compare_digest(row.code_hash, _hash(email, code)):
        row.attempts += 1
        left = settings.login_code_max_attempts - row.attempts
        if left <= 0:
            row.consumed_at = now
            db.commit()
            raise HTTPException(status_code=400, detail="Too many incorrect attempts. Request a new code.")
        db.commit()
        raise HTTPException(status_code=400, detail=f"That code isn't right. {left} attempt{'s' if left != 1 else ''} left.")
    row.consumed_at = now
    db.commit()
    return row


def account_for(db: Session, row: EmailCode, name: str | None = None) -> User:
    """The account a verified code signs in to: existing, or created now. Marks the email verified."""
    user = db.scalar(select(User).where(User.email == row.email))
    if user is None:
        payload = row.payload or {}
        user = User(
            email=row.email,
            name=(payload.get("name") or name or row.email.split("@")[0])[:100],
            # A registration code carries the chosen password hash; code sign-in creates a passwordless account.
            password_hash=payload.get("password_hash") or UNUSABLE_PASSWORD,
            preferences={},
        )
        db.add(user)
    # An existing account keeps its own password: a registration attempt for an address that
    # already has an account must never replace it.
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    db.commit()
    db.refresh(user)
    return user


def has_password(user: User) -> bool:
    return user.password_hash.startswith("scrypt$")
