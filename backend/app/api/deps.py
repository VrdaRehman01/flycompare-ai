from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_session_token
from app.models import User, UserSession

CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "FlyCompare"


def _as_aware(value: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_session_token(token)))
    if session is None:
        return None
    if _as_aware(session.expires_at) <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.user_id)


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


def require_csrf_header(request: Request) -> None:
    """Block cross-site form posts against cookie-authenticated endpoints.

    Browsers cannot attach a custom header to a cross-origin request without a
    CORS preflight, which our CORS policy only allows for configured origins.
    """
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status_code=403, detail="Missing request verification header.")
