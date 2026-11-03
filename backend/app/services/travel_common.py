"""Shared helpers for the non-flight travel products (stays, cars, tours, guides, planner).

Locations are accepted as an IATA airport/metro code (``DXB``) or a destination
key (``Dubai|AE``) and resolved to a ``City`` from the destination dataset, so
every product works for the same ~1,000 cities the Destinations page lists.
"""

import random
from datetime import date
from functools import lru_cache
from hashlib import sha256

from app.data.travel_content import CENTRES, DEFAULT_COST_INDEX, GUIDES, REGION_COST_INDEX, CityGuide
from app.services.airport_service import get_airport, metro_codes
from app.services.destination_service import City, cities

DEMO_NOTICE = (
    "No {product} provider is connected, so these options are simulated for the selected city and dates. "
    "Prices and availability are illustrative only and cannot be booked."
)


class LocationNotFound(ValueError):
    pass


class InvalidDates(ValueError):
    pass


@lru_cache(maxsize=1)
def _by_key() -> dict[str, City]:
    return {c.key: c for c in cities()}


@lru_cache(maxsize=1)
def _by_airport() -> dict[str, City]:
    return {a.code: c for c in cities() for a in c.airports}


def resolve_city(location: str) -> City:
    """Find the destination city for an airport code, metro code or ``City|CC`` key."""
    value = (location or "").strip()
    if "|" in value:
        city = _by_key().get(value)
        if city:
            return city
    code = value.upper()
    if len(code) == 3 and code.isalpha():
        found = _by_airport().get(code)
        if found:
            return found
        for member in metro_codes().get(code, ()):
            if member in _by_airport():
                return _by_airport()[member]
        airport = get_airport(code)
        if airport:
            # A smaller airport: use the nearest listed city sharing its city name, else build one.
            key = f"{airport.city}|{airport.country_code}"
            if key in _by_key():
                return _by_key()[key]
            return City(key, airport.city, airport.country, airport.country_code, airport.region, airport.lat, airport.lon, (airport,))
    raise LocationNotFound("Choose a city or airport from the list.")


def guide_for(city: City) -> CityGuide | None:
    return GUIDES.get(city.key)


def centre(city: City) -> tuple[float, float] | None:
    """City-centre coordinates when known (the dataset's city point is its main airport)."""
    return CENTRES.get(city.key)


def cost_index(city: City) -> float:
    guide = guide_for(city)
    if guide:
        return guide.cost_index
    return REGION_COST_INDEX.get(city.region, DEFAULT_COST_INDEX)


def seeded(*parts: object) -> random.Random:
    """A deterministic RNG so the same demo search always returns the same options."""
    digest = sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))  # nosec B311 - varies demo data only; security code uses `secrets`


def city_summary(city: City) -> dict:
    return {
        "key": city.key, "city": city.city, "country": city.country, "country_code": city.country_code,
        "region": city.region, "lat": city.lat, "lon": city.lon, "airport": city.primary.code,
        "airports": [{"code": a.code, "name": a.name} for a in city.airports],
    }


def check_range(start: date, end: date, *, today: date, max_days: int, label: str = "stay") -> int:
    if start < today:
        raise InvalidDates("Dates must be today or later.")
    if end <= start:
        raise InvalidDates(f"The end of the {label} must be after the start.")
    days = (end - start).days
    if days > max_days:
        raise InvalidDates(f"Choose a {label} of at most {max_days} days.")
    if (start - today).days > 365:
        raise InvalidDates("Choose dates within the next 12 months.")
    return days
