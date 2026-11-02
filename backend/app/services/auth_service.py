from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Response
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_session_token, new_session_token, verify_password
from app.models import (
    FareObservation,
    FavouriteDestination,
    FlightSearchHistory,
    RecentlyViewedFlight,
    SavedFlight,
    User,
    UserSession,
)
from app.schemas.account import Preferences, UserOut

# Used to equalise timing when an email is unknown, so login does not reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password-0")


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        preferences=Preferences(**(user.preferences or {})),
        created_at=user.created_at,
    )


def register(db: Session, name: str, email: str, password: str) -> User:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(name=name, email=email, password_hash=hash_password(password), preferences={})
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return user


def start_session(db: Session, user: User, response: Response) -> None:
    settings = get_settings()
    token = new_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
        )
    )
    # Opportunistically clear this user's expired sessions.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < datetime.now(timezone.utc)))
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def end_session(db: Session, token: str | None, response: Response) -> None:
    settings = get_settings()
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_session_token(token)))
        db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/", httponly=True, secure=settings.secure_cookies, samesite="lax")


def end_other_sessions(db: Session, user: User, keep_token: str | None) -> None:
    keep = hash_session_token(keep_token) if keep_token else ""
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != keep))


def delete_account(db: Session, user: User) -> None:
    """Remove the user and all of their personal records.

    Fare observations are anonymous price data; only their link to the user's
    search is removed so the deleted search history cannot be reconstructed.
    """
    search_ids = select(FlightSearchHistory.id).where(FlightSearchHistory.user_id == user.id)
    db.execute(update(FareObservation).where(FareObservation.search_id.in_(search_ids)).values(search_id=None))
    db.execute(delete(FlightSearchHistory).where(FlightSearchHistory.user_id == user.id))
    for model in (SavedFlight, RecentlyViewedFlight, FavouriteDestination, UserSession):
        db.execute(delete(model).where(model.user_id == user.id))
    db.delete(user)
    db.commit()
