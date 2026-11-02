import re
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models import FlightSearchHistory, User
from app.services import airport_service, analytics_service, destination_service, image_service, price_history_service, prediction_service, weather_service, deals_service
from app.services.currency_service import CurrencyUnavailable, get_rates
from app.services.history_service import history_rows

router = APIRouter(prefix="/api", tags=["insights"])

API_VERSION = "0.3.0"
FEATURES = ["auth", "insights", "airports", "nearby", "destinations", "images", "multi-city", "passenger-types", "price-history", "guides", "planner"]
# Services that only have simulated inventory so far; advertised only when explicitly enabled.
DEMO_FEATURES = ["stays", "cars", "transfers", "tours", "packages"]

Code = Annotated[str, Query(pattern=r"^[A-Z]{3}$")]
Cabin = Literal["Economy", "Premium economy", "Business", "First class"]


def _limit_lookup(request: Request) -> None:
    limiter.check(f"lookup:{request.client.host if request.client else 'unknown'}", 120)


@router.get("/insights/analytics", summary="Search analytics for the dashboard")
def analytics(
    range: Literal["7d", "30d", "90d", "all"] = "30d",
    scope: Literal["me", "all"] = "me",
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> dict:
    """`scope=me` covers the signed-in user's searches; `scope=all` is an anonymous aggregate of all searches."""
    if scope == "me" and user is None:
        raise HTTPException(status_code=401, detail="Sign in to see your personal insights.")
    data = analytics_service.compute_analytics(db, range, user.id if scope == "me" and user else None)
    if scope == "me" and user is not None:
        recent = db.scalars(
            select(FlightSearchHistory).where(FlightSearchHistory.user_id == user.id).order_by(FlightSearchHistory.created_at.desc()).limit(10)
        ).all()
        data["recent_searches"] = history_rows(recent)
    return data


@router.get("/prices/history", summary="Observed price history for one search")
def price_history(
    origin: Code,
    destination: Code,
    departure_date: date,
    return_date: date | None = None,
    cabin: Cabin = "Economy",
    trip_type: Literal["round-trip", "one-way"] = "round-trip",
    passengers: int = Query(default=1, ge=1, le=9),
    db: Session = Depends(get_db),
) -> dict:
    return price_history_service.route_history(db, origin, destination, departure_date, return_date, cabin, trip_type, passengers)


@router.get("/prices/routes", summary="Latest observed lowest fare per route")
def route_snapshots(routes: str = Query(max_length=400, description="Comma-separated, e.g. KHI-DXB,KHI-LHR"), db: Session = Depends(get_db)) -> list[dict]:
    pairs = []
    for item in routes.split(",")[:20]:
        match = re.fullmatch(r"([A-Z]{3})-([A-Z]{3})", item.strip())
        if not match:
            raise HTTPException(status_code=422, detail=f"Invalid route '{item}'. Use the form KHI-DXB.")
        pairs.append((match.group(1), match.group(2)))
    return price_history_service.latest_route_snapshots(db, pairs)


@router.get("/prices/estimate", summary="Model-based fare estimate (not a live fare)")
def fare_estimate(origin: Code, destination: Code, departure_date: date = Query()) -> dict:
    return prediction_service.estimate(origin, destination, departure_date)


@router.get("/currency/rates", summary="Reference exchange rates")
def currency_rates(base: str = Query(pattern=r"^[A-Z]{3}$")) -> dict:
    try:
        return get_rates(base)
    except CurrencyUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/airports", summary="Airport autocomplete", dependencies=[Depends(_limit_lookup)])
def airports(q: str = Query(min_length=2, max_length=60), limit: int = Query(default=10, ge=1, le=25)) -> list[dict]:
    """Search by city, airport name, IATA/ICAO code, metro code (LON, NYC) or country."""
    return airport_service.search_airports(q, limit)


@router.get("/airports/nearby", summary="Commercial airports near a location", dependencies=[Depends(_limit_lookup)])
def airports_nearby(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    limit: int = Query(default=5, ge=1, le=10),
) -> list[dict]:
    """Coordinates are used only for this lookup and are never stored or logged.

    The browser rounds them to ~1 km before sending.
    """
    return airport_service.nearby_airports(round(lat, 2), round(lon, 2), limit)


@router.get("/airports/map", summary="Major airports for the world map")
def airports_for_map() -> dict:
    """Compact list of large airports: [code, city, country, lat, lon]."""
    rows = [[a.code, a.city, a.country, a.lat, a.lon] for a in airport_service.dataset().airports if a.rank == 3]
    return {"fields": ["code", "city", "country", "lat", "lon"], "airports": rows, "source": airport_service.dataset().source}


@router.get("/airports/lookup", summary="Airport details for IATA codes")
def airports_lookup(codes: str = Query(max_length=200, description="Comma-separated IATA codes")) -> list[dict]:
    wanted = [c.strip().upper() for c in codes.split(",") if c.strip()][:40]
    if any(not re.fullmatch(r"[A-Z]{3}", c) for c in wanted):
        raise HTTPException(status_code=422, detail="Codes must be 3-letter IATA codes.")
    return airport_service.airports_for_codes(wanted)


@router.get("/destinations", summary="Global destination discovery")
def destinations(
    origin: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    q: str = Query(default="", max_length=60),
    region: str | None = Query(default=None, max_length=40),
    theme: Literal["Beach", "City", "Culture", "Nature", "Family", "Business"] | None = None,
    sort: Literal["popular", "distance", "name"] = "popular",
    scope: Literal["all", "seen", "nearby", "international"] = "all",
    page: int = Query(default=1, ge=1, le=200),
    page_size: int = Query(default=24, ge=1, le=60),
    db: Session = Depends(get_db),
) -> dict:
    return destination_service.list_destinations(db, origin, q, region, theme, sort, scope, page, page_size)


@router.get("/destinations/route", summary="What is known about a route from stored searches")
def destination_route(origin: Code, destination: Code, db: Session = Depends(get_db)) -> dict:
    o, d = airport_service.get_airport(origin), airport_service.get_airport(destination)
    if not o or not d:
        raise HTTPException(status_code=404, detail="Unknown airport code.")
    snapshot = price_history_service.latest_route_snapshots(db, [(origin, destination)])[0]
    return {
        "origin": o.to_dict(), "destination": d.to_dict(),
        "distance_km": round(airport_service.haversine_km(o.lat, o.lon, d.lat, d.lon)),
        "hubs": destination_service.route_hubs(db, origin, destination),
        "latest": snapshot,
        "note": "Connection hubs are airports seen in offers returned by FlyCompare searches, not a published airline schedule.",
    }


@router.get("/destinations/images", summary="Licensed destination photos with attribution", dependencies=[Depends(_limit_lookup)])
def destination_images(keys: str = Query(max_length=2000, description="Comma-separated City|CC keys, max 24"), db: Session = Depends(get_db)) -> list[dict]:
    """Photos are looked up and cached on the server. `pending: true` means the lookup was postponed (rate limit,
    network) and can be retried; `available: false` without `pending` means no freely licensed photo was found."""
    by_key = {c.key: c for c in destination_service.cities()}
    wanted = list({by_key[k].key: by_key[k] for k in (k.strip() for k in keys.split(",")) if k in by_key}.values())[:24]
    return image_service.images_for(db, wanted)


@router.get("/weather/discover", summary="Destinations grouped by forecast weather (Open-Meteo)", dependencies=[Depends(_limit_lookup)])
def weather_discover(
    on: date | None = Query(default=None, alias="date", description="Day to forecast (today to 15 days ahead)"),
    origin: Code | None = None,
    tz_offset_minutes: int | None = Query(default=None, ge=-840, le=720),
    db: Session = Depends(get_db),
) -> dict:
    """Weather is the provider's current conditions (today) or daily forecast (future day); never invented.
    Date validation uses the visitor's timezone when supplied, avoiding UTC/local date mismatches.
    With `origin`, the most recent observed fare to each destination is attached when one exists."""
    if origin and airport_service.get_airport(origin) is None:
        raise HTTPException(status_code=404, detail="Unknown airport code.")
    return weather_service.discover(db, on, origin, tz_offset_minutes=tz_offset_minutes)


@router.get("/prices/calendar", summary="Lowest observed fare per departure date (comparable searches only)")
def fare_calendar(
    origin: Code,
    destination: Code,
    start: date,
    end: date,
    trip_type: Literal["one-way", "round-trip"] = "round-trip",
    cabin: Cabin = "Economy",
    passengers: int = Query(default=1, ge=1, le=9),
    children: int = Query(default=0, ge=0, le=8),
    infants: int = Query(default=0, ge=0, le=9),
    db: Session = Depends(get_db),
) -> dict:
    if end < start or (end - start).days > 400:
        raise HTTPException(status_code=422, detail="Choose a window of up to about 13 months.")
    return price_history_service.fare_calendar(db, origin, destination, start, end, trip_type, cabin, passengers, children, infants)


@router.get("/deals", summary="Fares seen in earlier searches, grouped into comparable deals")
def list_deals(origin: Code | None = None, db: Session = Depends(get_db)) -> dict:
    if origin and airport_service.get_airport(origin) is None:
        raise HTTPException(status_code=404, detail="Unknown airport code.")
    return deals_service.deals(db, origin)


@router.get("/routes/popular", summary="Most searched routes: yours (signed in) or an anonymous aggregate")
def popular_routes(
    scope: Literal["me", "all"] = "all",
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> dict:
    if scope == "me" and user is None:
        raise HTTPException(status_code=401, detail="Sign in to see your routes.")
    return deals_service.popular_routes(db, scope, user.id if user else None, limit)


@router.get("/prices/route-history", summary="Lowest observed fare per day for a route, any travel date")
def route_price_history(origin: Code, destination: Code, db: Session = Depends(get_db)) -> dict:
    return price_history_service.route_daily_lowest(db, origin, destination)


@router.get("/meta", summary="API version and capabilities")
def meta() -> dict:
    """Lets the frontend detect an outdated or missing API server."""
    settings = get_settings()
    features = FEATURES + (DEMO_FEATURES if settings.demo_travel_services_enabled else [])
    return {"service": "flycompare-api", "api_version": API_VERSION, "features": features}
