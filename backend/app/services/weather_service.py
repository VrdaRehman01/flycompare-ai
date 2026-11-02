"""Weather-based destination discovery.

Covers the curated destinations (see destination_service.CURATED). Each city is
placed in categories by explicit rules applied to the provider's forecast for
the chosen day; the rules are returned with the data so the UI can show them.
Results are cached briefly per day to keep provider traffic low.
"""

import threading
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.providers.weather_provider import MAX_FORECAST_DAYS, OpenMeteoProvider, Point, WeatherUnavailable
from app.services import destination_service, price_history_service

CACHE_SECONDS = 30 * 60

CATEGORIES: dict[str, tuple[str, str]] = {
    "sunny": ("Sunny", "Clear, mainly clear or partly cloudy sky, and not rainy"),
    "warm": ("Warm", "Daytime high of 26 °C or more"),
    "cool": ("Cool weather", "Daytime high of 16 °C or less, no snow"),
    "snow": ("Snow", "Snow forecast, or a snowfall total above 0 cm"),
    "beach": ("Beach weather", "Beach destination with a high of 25 °C or more and no rain"),
    "city": ("Pleasant city break", "City or culture destination, high between 16 and 27 °C, no rain"),
    "rainy": ("Rainy", "2 mm of rain or more, or rain/storms with a 50% or higher chance of precipitation"),
}

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def categorise(day: dict, themes: tuple[str, ...]) -> list[str]:
    """Categories for one day's forecast. Missing values never satisfy a rule."""
    hi, rain, snow, icon = day.get("max_c"), day.get("precipitation_mm"), day.get("snowfall_cm"), day.get("icon")
    chance = day.get("precipitation_probability")
    # The daily code is the most severe weather at any hour, so a brief shower alone does not make a rainy day.
    rainy = (rain is not None and rain >= 2) or (icon in {"rain", "storm"} and (chance is None or chance >= 50))
    snowy = icon == "snow" or (snow is not None and snow > 0)
    out = []
    if icon in {"clear", "partly-cloudy"} and not rainy and not snowy:
        out.append("sunny")
    if hi is not None and hi >= 26:
        out.append("warm")
    if hi is not None and hi <= 16 and not snowy:
        out.append("cool")
    if snowy:
        out.append("snow")
    if "Beach" in themes and hi is not None and hi >= 25 and not rainy:
        out.append("beach")
    if {"City", "Culture"} & set(themes) and hi is not None and 16 <= hi <= 27 and not rainy and not snowy:
        out.append("city")
    if rainy:
        out.append("rainy")
    return out


def _forecast(on: date, provider: OpenMeteoProvider) -> dict:
    key = on.isoformat()
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
    cities = [c for c in destination_service.cities() if c.key in destination_service.CURATED]
    data = provider.forecast([Point(c.key, c.lat, c.lon) for c in cities], on, days=1)
    result = {"cities": cities, "data": data}
    with _lock:
        _cache[key] = (time.monotonic(), result)
    return result


def today_for_timezone(tz_offset_minutes: int | None = None, now_utc: datetime | None = None) -> date:
    """Return today's calendar date for the browser timezone offset.

    JavaScript Date.getTimezoneOffset() is UTC minus local time, so subtracting
    that offset from UTC produces the visitor's local wall-clock date.
    """
    if tz_offset_minutes is None:
        return date.today()
    utc_now = now_utc or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    return (utc_now.astimezone(timezone.utc) - timedelta(minutes=tz_offset_minutes)).date()


def discover(
    db: Session,
    on: date | None = None,
    origin: str | None = None,
    provider: OpenMeteoProvider | None = None,
    tz_offset_minutes: int | None = None,
) -> dict:
    # Date inputs are calendar dates in the visitor's timezone. The API server may
    # run in UTC, which can be a different calendar day from the browser.
    today = today_for_timezone(tz_offset_minutes)
    on = on or today
    provider = provider or OpenMeteoProvider()
    base = {
        "date": on.isoformat(),
        "provider": provider.name,
        "attribution": provider.attribution,
        "categories": [{"key": k, "label": label, "rule": rule} for k, (label, rule) in CATEGORIES.items()],
    }
    if on < today:
        return {**base, "available": False, "reason": "Choose today or a future date. Past weather is not shown here."}
    if on > today + timedelta(days=MAX_FORECAST_DAYS - 1):
        return {**base, "available": False,
                "reason": f"Forecasts only cover the next {MAX_FORECAST_DAYS} days. Pick a closer date, or check again nearer to your trip."}
    try:
        cached = _forecast(on, provider)
    except WeatherUnavailable as exc:
        return {**base, "available": False, "reason": f"{exc} Please try again later."}

    cities, data = cached["cities"], cached["data"]
    fares = {}
    if origin:
        routes = [(origin, c.airports[0].code) for c in cities if c.airports and c.airports[0].code != origin]
        fares = {s["destination"]: s for s in price_history_service.latest_route_snapshots(db, routes) if s.get("available")}
    items = []
    for c in cities:
        weather = data.get(c.key)
        day = (weather or {}).get("daily", [None])[0] if weather else None
        if not day:
            continue
        themes = destination_service.CURATED.get(c.key, ())
        airport = c.airports[0].code if c.airports else None
        items.append({
            "key": c.key, "city": c.city, "country": c.country, "country_code": c.country_code, "airport": airport,
            "themes": list(themes),
            "kind": "current" if on == today else "forecast",
            "current": weather["current"] if on == today else None,
            "day": day,
            "timezone": weather.get("timezone"),
            "utc_offset_seconds": weather.get("utc_offset_seconds"),
            "retrieved_at": weather.get("retrieved_at"),
            "categories": categorise(day, themes),
            "fare": fares.get(airport),
        })
    return {**base, "available": True, "kind": "current" if on == today else "forecast", "items": items}
