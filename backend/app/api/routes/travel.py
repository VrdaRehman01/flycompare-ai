"""Travel products beyond flights: stays, cars, transfers, tours, guides and the trip planner."""

from datetime import date, datetime, time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.rate_limit import limit_search, limiter
from app.data.travel_content import CATEGORIES
from app.providers.stays_provider import search_stays
from app.services import ground_service, guide_service, media_service, planner_service, tours_service
from app.services.travel_common import InvalidDates, LocationNotFound, check_range, city_summary, resolve_city

router = APIRouter(prefix="/api", tags=["travel"])

Location = Annotated[str, Query(min_length=3, max_length=80, description="Airport/metro code (DXB) or destination key (Dubai|AE)")]


def _limit(request: Request) -> None:
    limiter.check(f"travel:{request.client.host if request.client else 'unknown'}", 60)


def _demo_services() -> None:
    """Stays, cars, transfers and tours have no real inventory provider yet."""
    if not get_settings().demo_travel_services_enabled:
        raise HTTPException(status_code=404, detail="This service is not available yet.")


def _city(location: str):
    try:
        return resolve_city(location)
    except LocationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _range(start: date, end: date, max_days: int, label: str) -> int:
    try:
        return check_range(start, end, today=date.today(), max_days=max_days, label=label)
    except InvalidDates as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/stays/search", summary="Hotels, apartments and other stays in a city", dependencies=[Depends(_demo_services), Depends(limit_search)])
def stays_search(
    location: Location,
    check_in: date,
    check_out: date,
    adults: int = Query(default=2, ge=1, le=16),
    children: int = Query(default=0, ge=0, le=8),
    rooms: int = Query(default=1, ge=1, le=8),
) -> dict:
    nights = _range(check_in, check_out, 30, "stay")
    if rooms > adults:
        raise HTTPException(status_code=422, detail="Each room needs at least one adult.")
    city = _city(location)
    result = search_stays(get_settings(), city, check_in, check_out, adults, children, rooms)
    return {"city": city_summary(city), "check_in": check_in, "check_out": check_out, "nights": nights,
            "adults": adults, "children": children, "rooms": rooms, **result}


@router.get("/cars/search", summary="Car rental at an airport", dependencies=[Depends(_demo_services), Depends(_limit)])
def cars_search(
    location: Location,
    pickup_date: date,
    dropoff_date: date,
    pickup_time: time = Query(default=time(10)),
    dropoff_time: time = Query(default=time(10)),
    driver_age: int = Query(default=30, ge=18, le=99),
) -> dict:
    pickup, dropoff = datetime.combine(pickup_date, pickup_time), datetime.combine(dropoff_date, dropoff_time)
    if pickup_date < date.today() or (pickup_date - date.today()).days > 365:
        raise HTTPException(status_code=422, detail="Choose a pick-up date within the next 12 months.")
    if dropoff <= pickup:
        raise HTTPException(status_code=422, detail="Drop-off must be after pick-up.")
    if (dropoff - pickup).days > 60:
        raise HTTPException(status_code=422, detail="Choose a rental of at most 60 days.")
    city = _city(location)
    code = location.upper() if len(location) == 3 else None
    return {"city": city_summary(city), **ground_service.search_cars(city, code, pickup, dropoff, driver_age)}


@router.get("/transfers/search", summary="Airport transfers to or from the city", dependencies=[Depends(_demo_services), Depends(_limit)])
def transfers_search(
    location: Location,
    on: date = Query(alias="date"),
    at: time = Query(default=time(12), alias="time"),
    passengers: int = Query(default=2, ge=1, le=14),
    bags: int = Query(default=2, ge=0, le=20),
    direction: Literal["from_airport", "to_airport"] = "from_airport",
) -> dict:
    if on < date.today():
        raise HTTPException(status_code=422, detail="Choose today or a later date.")
    city = _city(location)
    code = location.upper() if len(location) == 3 else None
    return {"city": city_summary(city), "direction": direction, "passengers": passengers, "bags": bags,
            **ground_service.search_transfers(city, code, on, at, passengers, bags, direction)}


@router.get("/tours/search", summary="Group or private tours in a city", dependencies=[Depends(_demo_services), Depends(_limit)])
def tours_search(
    location: Location,
    on: date = Query(alias="date"),
    travellers: int = Query(default=2, ge=1, le=20),
    kind: Literal["group", "private"] = "group",
) -> dict:
    if on < date.today():
        raise HTTPException(status_code=422, detail="Choose today or a later date.")
    city = _city(location)
    return {"city": city_summary(city), "date": on, "travellers": travellers, **tours_service.search_tours(city, on, travellers, kind)}


@router.get("/media/photo", summary="Freely licensed photo for a sight, car model, vehicle or property type")
def media_photo(
    request: Request,
    kind: Literal["article", "stay"] = "article",
    q: str = Query(min_length=2, max_length=120),
    seed: str = Query(default="", max_length=80),
    context: str = Query(default="", max_length=80, description="Optional place name tried with the query first"),
) -> dict:
    limiter.check(f"media:{request.client.host if request.client else 'unknown'}", 300)
    return media_service.photo(kind, q, seed, context)


@router.get("/guides", summary="Cities with a curated travel guide")
def guides_list() -> dict:
    return {"items": guide_service.list_guides(), "categories": list(CATEGORIES)}


@router.get("/guides/detail", summary="Travel guide for a city", dependencies=[Depends(_limit)])
def guide_detail(location: Location) -> dict:
    try:
        return guide_service.guide_detail(location)
    except LocationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class PlanRequest(BaseModel):
    location: str = Field(min_length=3, max_length=80)
    start: date
    end: date
    travellers: int = Field(default=2, ge=1, le=12)
    interests: list[Literal["Culture", "Nature", "Beach", "Family", "City", "Food", "Shopping", "Adventure"]] = Field(default_factory=list, max_length=8)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    budget: Literal["budget", "mid", "luxury"] = "mid"


@router.post("/planner/plan", summary="Day-by-day trip plan with weather and a budget estimate", dependencies=[Depends(_limit)])
def plan(body: PlanRequest) -> dict:
    _range(body.start, body.end, 21, "trip")
    city = _city(body.location)
    return planner_service.plan_trip(city, body.start, body.end, body.travellers, body.interests, body.pace, body.budget)
