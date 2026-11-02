from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf_header
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limit_auth
from app.core.security import hash_password, verify_password
from app.models import FavouriteDestination, FlightSearchHistory, RecentlyViewedFlight, SavedFlight, SavedRoute, User, utcnow
from app.schemas.account import (
    DeleteAccountRequest,
    FavouriteRequest,
    PasswordChange,
    Preferences,
    ProfileUpdate,
    SavedFlightOut,
    SavedRouteRequest,
    SaveFlightRequest,
    UserOut,
)
from app.services import airport_service, auth_service, deals_service
from app.services.history_service import history_rows

router = APIRouter(prefix="/api/account", tags=["account"], dependencies=[Depends(require_csrf_header)])

MAX_SAVED_FLIGHTS = 200
MAX_RECENTLY_VIEWED = 20
MAX_SAVED_ROUTES = 100


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)) -> UserOut:
    return auth_service.user_out(user)


@router.patch("/profile", response_model=UserOut)
def update_profile(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    if body.email and body.email != user.email:
        # Changing the sign-in email requires the current password.
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Enter your current password to change your email.")
        if db.scalar(select(User.id).where(User.email == body.email, User.id != user.id)) is not None:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        user.email = body.email
    if body.name:
        user.name = body.name
    db.commit()
    db.refresh(user)
    return auth_service.user_out(user)


@router.put("/preferences", response_model=UserOut)
def update_preferences(body: Preferences, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    user.preferences = body.model_dump()
    db.commit()
    db.refresh(user)
    return auth_service.user_out(user)


@router.post("/password", status_code=204, dependencies=[Depends(limit_auth)])
def change_password(body: PasswordChange, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    # Sign out every other device; keep the current session.
    auth_service.end_other_sessions(db, user, request.cookies.get(get_settings().session_cookie_name))
    db.commit()
    return Response(status_code=204)


@router.post("/delete", status_code=204, dependencies=[Depends(limit_auth)])
def delete_account(body: DeleteAccountRequest, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password is incorrect.")
    auth_service.delete_account(db, user)
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/", httponly=True, secure=settings.secure_cookies, samesite="lax")
    response.status_code = 204
    return response


# ----------------------------------------------------------------- history


@router.get("/history")
def get_history(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(limit, 200))
    rows = db.scalars(
        select(FlightSearchHistory).where(FlightSearchHistory.user_id == user.id).order_by(FlightSearchHistory.created_at.desc()).limit(limit)
    ).all()
    return history_rows(rows)


@router.delete("/history", status_code=204)
def clear_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    # Searches are detached from the account rather than kept as personal history.
    rows = db.scalars(select(FlightSearchHistory).where(FlightSearchHistory.user_id == user.id)).all()
    for row in rows:
        row.user_id = None
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------ saved flights


def _saved_out(row: SavedFlight) -> SavedFlightOut:
    return SavedFlightOut(id=row.id, offer_id=row.offer_id, offer=row.offer, search=row.search, saved_at=row.created_at)


@router.get("/saved-flights", response_model=list[SavedFlightOut])
def list_saved(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SavedFlightOut]:
    rows = db.scalars(select(SavedFlight).where(SavedFlight.user_id == user.id).order_by(SavedFlight.created_at.desc())).all()
    return [_saved_out(r) for r in rows]


@router.post("/saved-flights", response_model=SavedFlightOut, status_code=201)
def save_flight(body: SaveFlightRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SavedFlightOut:
    offer_id = body.offer["id"]
    existing = db.scalar(select(SavedFlight).where(SavedFlight.user_id == user.id, SavedFlight.offer_id == offer_id))
    if existing:
        return _saved_out(existing)
    count = db.scalar(select(func.count()).select_from(SavedFlight).where(SavedFlight.user_id == user.id)) or 0
    if count >= MAX_SAVED_FLIGHTS:
        raise HTTPException(status_code=400, detail=f"You can save up to {MAX_SAVED_FLIGHTS} flights. Remove some first.")
    row = SavedFlight(user_id=user.id, offer_id=offer_id, offer=body.offer, search=body.search)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _saved_out(row)


@router.delete("/saved-flights/{saved_id}", status_code=204)
def unsave_flight(saved_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    row = db.get(SavedFlight, saved_id)
    # Treat other users' records as not found so their existence is not revealed.
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved flight not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------- recently viewed


@router.get("/recently-viewed", response_model=list[SavedFlightOut])
def list_recent(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SavedFlightOut]:
    rows = db.scalars(
        select(RecentlyViewedFlight).where(RecentlyViewedFlight.user_id == user.id).order_by(RecentlyViewedFlight.viewed_at.desc()).limit(MAX_RECENTLY_VIEWED)
    ).all()
    return [SavedFlightOut(id=r.id, offer_id=r.offer_id, offer=r.offer, search=r.search, saved_at=r.viewed_at) for r in rows]


@router.post("/recently-viewed", status_code=204)
def add_recent(body: SaveFlightRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    offer_id = body.offer["id"]
    row = db.scalar(select(RecentlyViewedFlight).where(RecentlyViewedFlight.user_id == user.id, RecentlyViewedFlight.offer_id == offer_id))
    if row:
        row.viewed_at = utcnow()
        row.offer = body.offer
        row.search = body.search
    else:
        db.add(RecentlyViewedFlight(user_id=user.id, offer_id=offer_id, offer=body.offer, search=body.search))
    db.flush()
    stale = db.scalars(
        select(RecentlyViewedFlight.id).where(RecentlyViewedFlight.user_id == user.id).order_by(RecentlyViewedFlight.viewed_at.desc()).offset(MAX_RECENTLY_VIEWED)
    ).all()
    if stale:
        db.execute(delete(RecentlyViewedFlight).where(RecentlyViewedFlight.id.in_(stale)))
    db.commit()
    return Response(status_code=204)


@router.delete("/recently-viewed", status_code=204)
def clear_recent(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    db.execute(delete(RecentlyViewedFlight).where(RecentlyViewedFlight.user_id == user.id))
    db.commit()
    return Response(status_code=204)


# -------------------------------------------------------------- favourites


@router.get("/favourites", response_model=list[str])
def list_favourites(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(select(FavouriteDestination.airport_code).where(FavouriteDestination.user_id == user.id).order_by(FavouriteDestination.created_at)))


@router.post("/favourites", response_model=list[str], status_code=201)
def add_favourite(body: FavouriteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[str]:
    exists = db.scalar(select(FavouriteDestination.id).where(FavouriteDestination.user_id == user.id, FavouriteDestination.airport_code == body.airport_code))
    if exists is None:
        db.add(FavouriteDestination(user_id=user.id, airport_code=body.airport_code))
        db.commit()
    return list_favourites(user, db)


@router.delete("/favourites/{code}", response_model=list[str])
def remove_favourite(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[str]:
    db.execute(delete(FavouriteDestination).where(FavouriteDestination.user_id == user.id, FavouriteDestination.airport_code == code.upper()))
    db.commit()
    return list_favourites(user, db)


# ------------------------------------------------------------ saved routes


@router.get("/saved-routes")
def list_saved_routes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return deals_service.saved_routes(db, user.id)


@router.post("/saved-routes", status_code=201)
def save_route(body: SavedRouteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    if body.origin == body.destination:
        raise HTTPException(status_code=422, detail="Origin and destination must be different.")
    if airport_service.get_airport(body.origin) is None or airport_service.get_airport(body.destination) is None:
        raise HTTPException(status_code=404, detail="Unknown airport code.")
    exists = db.scalar(select(SavedRoute.id).where(SavedRoute.user_id == user.id, SavedRoute.origin_code == body.origin, SavedRoute.destination_code == body.destination))
    if exists is None:
        if db.scalar(select(func.count()).select_from(SavedRoute).where(SavedRoute.user_id == user.id)) >= MAX_SAVED_ROUTES:
            raise HTTPException(status_code=409, detail=f"You can save up to {MAX_SAVED_ROUTES} routes. Remove one first.")
        db.add(SavedRoute(user_id=user.id, origin_code=body.origin, destination_code=body.destination))
        db.commit()
    return deals_service.saved_routes(db, user.id)


@router.delete("/saved-routes/{origin}/{destination}")
def remove_saved_route(origin: str, destination: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    db.execute(delete(SavedRoute).where(SavedRoute.user_id == user.id, SavedRoute.origin_code == origin.upper(), SavedRoute.destination_code == destination.upper()))
    db.commit()
    return deals_service.saved_routes(db, user.id)
