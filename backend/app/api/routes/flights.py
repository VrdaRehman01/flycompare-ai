import logging
import os
from datetime import date, datetime, timedelta, timezone
import sys
from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, require_csrf_header
from app.core.config import BACKEND_DIR, ENV_FILES, REPO_ROOT, get_settings
from app.core.database import get_db
from app.core.rate_limit import limit_search, limiter
from app.models import FlightSearchHistory, User
from app.providers.errors import FlightProviderError
from app.providers.factory import ProviderConfigError, build_flight_provider
from app.schemas.flight import FlightSearchRequest, FlightSearchResponse, NearbyDate
from app.services import search_service
from app.services.history_service import history_rows

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/flights", tags=["flights"])

# This marker lets us verify that Uvicorn is serving this exact replacement.
ROUTE_BUILD_MARKER = "provider-diagnostic-2026-10-31-v2"


def get_flight_provider():
    """Construct the provider selected by the settings of this process."""
    try:
        return build_flight_provider(get_settings())
    except ProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/provider", summary="Diagnose the active flight provider", include_in_schema=False)
def provider_diagnostic() -> dict:
    """Development-only diagnostics; never returns the API token or its contents.

    Outside development it does not exist (404): configuration details are not public.
    """
    settings = get_settings()
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Not Found")
    provider, data_status = get_flight_provider()
    token = settings.duffel_access_token or ""
    info = {
        "build_marker": ROUTE_BUILD_MARKER,
        "configured_provider": settings.flight_provider.strip().lower(),
        "active_provider_class": type(provider).__name__,
        "data_status": data_status,
        "duffel_token_configured": bool(token),
        "duffel_token_type": ("test" if token.startswith("duffel_test_") else "live/other") if token else "missing",
    }
    # Filesystem details are only useful while developing locally.
    if settings.app_env.strip().lower() in {"development", "dev", "local"}:
        info.update(
            {
                "backend_directory": str(BACKEND_DIR),
                "repository_directory": str(REPO_ROOT),
                "config_module": str(FilePath(sys.modules["app.core.config"].__file__).resolve()),
                "routes_module": str(FilePath(__file__).resolve()),
                "working_directory": os.getcwd(),
                "env_files_checked": [str(path) for path in ENV_FILES],
            }
        )
    return info


@router.post("/search", response_model=FlightSearchResponse, summary="Search flight offers", dependencies=[Depends(require_csrf_header), Depends(limit_search)])
def search_flights(
    request: FlightSearchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> FlightSearchResponse:
    # Airports' local dates can be up to a day ahead of UTC, so allow "yesterday" in UTC.
    earliest = date.today() - timedelta(days=1)
    dates = [request.departure_date] + ([leg.departure_date for leg in request.legs] if request.legs else [])
    if min(dates) < earliest:
        raise HTTPException(status_code=422, detail="Departure dates cannot be in the past.")

    provider, data_status = get_flight_provider()
    logger.info("Flight search using provider=%s data_status=%s", type(provider).__name__, data_status)

    try:
        results = provider.search(request)
    except FlightProviderError as exc:
        logger.warning("Flight search failed (%s): %s", type(provider).__name__, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    history = search_service.record_search(db, request, results, provider.name, data_status, user)
    response = search_service.build_response(results, data_status, provider.name, history.id)
    if not results and hasattr(provider, "nearby_dates"):
        try:
            response.nearby_dates = [NearbyDate(**d) for d in provider.nearby_dates(request)]
        except FlightProviderError as exc:
            logger.warning("Nearby dates unavailable (%s): %s", type(provider).__name__, exc)
    return response


@router.get("/history", summary="Get the signed-in user's recent searches")
def get_search_history(db: Session = Depends(get_db), user: User | None = Depends(get_current_user_optional)) -> list[dict]:
    """Return the 50 most recent searches of the signed-in user.

    Anonymous visitors get an empty list: search history is personal data and is
    never shared between visitors.
    """
    if user is None:
        return []
    searches = db.scalars(
        select(FlightSearchHistory).where(FlightSearchHistory.user_id == user.id).order_by(FlightSearchHistory.created_at.desc()).limit(50)
    ).all()
    return history_rows(searches)


@router.get("/analytics", summary="Aggregate search summary (legacy shape)")
def get_search_analytics(db: Session = Depends(get_db)) -> dict:
    """Anonymous aggregate over all searches. See /api/insights/analytics for the full dashboard."""
    searches = db.scalars(select(FlightSearchHistory).order_by(FlightSearchHistory.created_at.desc())).all()
    destination_counts: dict[str, int] = {}
    for search in searches:
        destination = (search.destination_code or search.destination).strip()
        destination_counts[destination] = destination_counts.get(destination, 0) + 1
    most = max(destination_counts, key=destination_counts.get) if destination_counts else None
    return {
        "total_searches": len(searches),
        "unique_destinations": len(destination_counts),
        "most_searched_destination": most,
        "destination_counts": destination_counts,
        "latest_search": (
            {"origin": searches[0].origin_code or searches[0].origin, "destination": searches[0].destination_code or searches[0].destination, "created_at": searches[0].created_at}
            if searches
            else None
        ),
    }


def _limit_offer_lookup(request: Request) -> None:
    if get_settings().rate_limit_enabled:
        limiter.check(f"offer:{request.client.host if request.client else 'unknown'}", 30)


def _provider_call(capability: str, offer_id: str):
    """Run an on-demand offer call on the active provider, or report that it is not supported."""
    provider, data_status = get_flight_provider()
    method = getattr(provider, capability, None)
    if method is None:
        return None, data_status
    try:
        return method(offer_id), data_status
    except FlightProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/offers/{offer_id}/seat-maps", summary="Seat maps for an offer (when the airline supplies them)",
            dependencies=[Depends(_limit_offer_lookup)])
def offer_seat_maps(offer_id: str = Path(max_length=80)) -> dict:
    maps, data_status = _provider_call("seat_maps", offer_id)
    if maps is None:
        return {"supported": False, "data_status": data_status, "seat_maps": [],
                "message": "Seat selection is not available for this offer through the current provider."}
    return {"supported": True, "data_status": data_status, "seat_maps": maps,
            "message": None if maps else "The airline did not supply a seat map for this offer."}


@router.get("/offers/{offer_id}", summary="Re-check an offer: current price, expiry and extra bags",
            dependencies=[Depends(_limit_offer_lookup)])
def offer_details(offer_id: str = Path(max_length=80)) -> dict:
    details, data_status = _provider_call("offer_details", offer_id)
    if details is None:
        return {"supported": False, "data_status": data_status,
                "message": "This provider does not support re-checking offers or adding extras."}
    return {"supported": True, "data_status": data_status, "checked_at": datetime.now(timezone.utc).isoformat(), **details}
