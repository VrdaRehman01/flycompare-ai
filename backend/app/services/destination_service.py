"""Global destination discovery.

Destinations are cities with at least one major airport in the airport dataset.
Theme tags (Beach, City, Culture…) are an editorial classification for a set of
well-known destinations and are labelled as curated. Route information is only
ever reported from stored provider observations ("seen in searches"); nothing
here claims that an airline operates a route.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FareObservation
from app.services.airport_service import HUB_BONUS, Airport, dataset, fold, get_airport, haversine_km, region_for

THEMES = ("Beach", "City", "Culture", "Nature", "Family", "Business")

# Editorial tags for popular destinations, in rough order of global popularity.
CURATED: dict[str, tuple[str, ...]] = {
    "Dubai|AE": ("City", "Beach", "Family", "Business"), "London|GB": ("City", "Culture", "Business"),
    "Paris|FR": ("City", "Culture"), "Istanbul|TR": ("City", "Culture"), "Bangkok|TH": ("City", "Culture"),
    "New York|US": ("City", "Culture", "Business"), "Singapore|SG": ("City", "Family", "Business"),
    "Tokyo|JP": ("City", "Culture", "Business"), "Doha|QA": ("City", "Business"), "Kuala Lumpur|MY": ("City", "Culture"),
    "Rome|IT": ("Culture", "City"), "Barcelona|ES": ("Beach", "City", "Culture"), "Hong Kong|HK": ("City", "Business"),
    "Jeddah|SA": ("Culture", "Beach"), "Medina|SA": ("Culture",), "Riyadh|SA": ("Business", "City"),
    "Abu Dhabi|AE": ("Family", "Culture", "Business"), "Cairo|EG": ("Culture",), "Marrakesh|MA": ("Culture",),
    "Malé|MV": ("Beach", "Nature"), "Denpasar|ID": ("Beach", "Nature", "Culture"), "Phuket|TH": ("Beach", "Family"),
    "Colombo|LK": ("Beach", "Culture", "Nature"), "Kathmandu|NP": ("Nature", "Culture"), "Baku|AZ": ("City", "Culture"),
    "Tbilisi|GE": ("Culture", "Nature"), "Amsterdam|NL": ("City", "Culture"), "Madrid|ES": ("City", "Culture"),
    "Lisbon|PT": ("City", "Culture", "Beach"), "Athens|GR": ("Culture", "Beach"), "Prague|CZ": ("Culture", "City"),
    "Vienna|AT": ("Culture", "City"), "Zurich|CH": ("Nature", "Business"), "Geneva|CH": ("Nature", "Business"),
    "Munich|DE": ("Culture", "Business"), "Frankfurt|DE": ("Business",), "Berlin|DE": ("City", "Culture"),
    "Milan|IT": ("City", "Business"), "Venice|IT": ("Culture",), "Antalya|TR": ("Beach", "Family"),
    "Manchester|GB": ("City", "Business"), "Edinburgh|GB": ("Culture", "Nature"), "Dublin|IE": ("City", "Culture"),
    "Copenhagen|DK": ("City", "Culture"), "Stockholm|SE": ("City", "Nature"), "Oslo|NO": ("Nature", "City"),
    "Reykjavik|IS": ("Nature",), "Los Angeles|US": ("City", "Beach", "Family"), "San Francisco|US": ("City", "Business"),
    "Miami|US": ("Beach", "City"), "Orlando|US": ("Family",), "Chicago|US": ("City", "Business"),
    "Toronto|CA": ("City", "Business"), "Vancouver|CA": ("Nature", "City"), "Cancún|MX": ("Beach", "Family"),
    "Mexico City|MX": ("City", "Culture"), "Rio de Janeiro|BR": ("Beach", "City"), "São Paulo|BR": ("City", "Business"),
    "Buenos Aires|AR": ("City", "Culture"), "Lima|PE": ("Culture",), "Cape Town|ZA": ("Nature", "Beach"),
    "Johannesburg|ZA": ("Business", "City"), "Nairobi|KE": ("Nature", "Business"), "Zanzibar|TZ": ("Beach",),
    "Seoul|KR": ("City", "Culture", "Business"), "Osaka|JP": ("City", "Culture", "Family"), "Shanghai|CN": ("City", "Business"),
    "Beijing|CN": ("Culture", "Business"), "Taipei|TW": ("City", "Culture"), "Manila|PH": ("City",),
    "Ho Chi Minh City|VN": ("City", "Culture"), "Hanoi|VN": ("Culture", "Nature"), "Sydney|AU": ("City", "Beach", "Family"),
    "Melbourne|AU": ("City", "Culture"), "Auckland|NZ": ("Nature", "City"), "Delhi|IN": ("Culture", "Business"),
    "Mumbai|IN": ("City", "Business"), "Goa|IN": ("Beach",), "Muscat|OM": ("Nature", "Culture"), "Manama|BH": ("Business",),
    "Kuwait City|KW": ("Business",), "Amman|JO": ("Culture",), "Lahore|PK": ("Culture", "City"),
    "Islamabad|PK": ("Nature", "Business"), "Karachi|PK": ("City", "Business", "Beach"),
}
POPULARITY = {key: i for i, key in enumerate(CURATED)}


@dataclass(frozen=True)
class City:
    key: str
    city: str
    country: str
    country_code: str
    region: str
    lat: float
    lon: float
    airports: tuple[Airport, ...]

    @property
    def primary(self) -> Airport:
        return self.airports[0]


@lru_cache(maxsize=1)
def cities() -> tuple[City, ...]:
    groups: dict[str, list[Airport]] = defaultdict(list)
    for a in dataset().airports:
        key = f"{a.city}|{a.country_code}"
        if a.rank == 3 or key in CURATED:
            groups[key].append(a)
    out = []
    for key, airports in groups.items():
        airports.sort(key=lambda a: (-a.rank, -HUB_BONUS.get(a.code, 0), a.code))
        p = airports[0]
        out.append(City(key, p.city, p.country, p.country_code, region_for(p.country_code, p.continent), p.lat, p.lon, tuple(airports)))
    return tuple(out)


def regions() -> list[str]:
    return sorted({c.region for c in cities()})


def _observed_routes(db: Session, origin: str) -> dict[str, dict]:
    """Destinations seen in stored provider offers from this origin."""
    rows = db.execute(
        select(
            FareObservation.destination_code,
            func.min(FareObservation.stops),
            func.max(FareObservation.observed_at),
            func.count(func.distinct(FareObservation.search_id)),
        )
        .where(FareObservation.origin_code == origin)
        .group_by(FareObservation.destination_code)
    ).all()
    seen = {}
    for dest, min_stops, last, searches in rows:
        seen[dest] = {
            "status": "seen_in_searches",
            "direct_seen": min_stops == 0,
            "last_seen": last if last.tzinfo else last.replace(tzinfo=timezone.utc),
            "searches": searches,
        }
    return seen


def list_destinations(
    db: Session,
    origin: str | None = None,
    q: str = "",
    region: str | None = None,
    theme: str | None = None,
    sort: str = "popular",
    scope: str = "all",
    page: int = 1,
    page_size: int = 24,
) -> dict:
    origin_airport = get_airport(origin) if origin else None
    observed = _observed_routes(db, origin_airport.code) if origin_airport else {}
    query = fold(q)

    items = []
    for c in cities():
        if origin_airport and c.key == f"{origin_airport.city}|{origin_airport.country_code}":
            continue
        tags = CURATED.get(c.key, ())
        if region and c.region != region:
            continue
        if theme and theme not in tags:
            continue
        if query and not (
            fold(c.city).startswith(query) or fold(c.country).startswith(query) or query in fold(c.city)
            or any(a.code.casefold() == query or fold(a.name).startswith(query) for a in c.airports)
        ):
            continue
        distance = haversine_km(origin_airport.lat, origin_airport.lon, c.lat, c.lon) if origin_airport else None
        seen = [observed[a.code] | {"airport": a.code} for a in c.airports if a.code in observed]
        if scope == "seen" and not seen:
            continue
        if scope == "nearby" and (distance is None or distance > 2500):
            continue
        if scope == "international" and origin_airport and c.country_code == origin_airport.country_code:
            continue
        items.append((c, tags, distance, seen))

    if sort == "distance" and origin_airport:
        items.sort(key=lambda x: x[2])
    elif sort == "name":
        items.sort(key=lambda x: (fold(x[0].city), x[0].country))
    else:  # popular: routes seen in searches, then curated popularity, then airport importance
        items.sort(key=lambda x: (0 if x[3] else 1, POPULARITY.get(x[0].key, 10_000), -len(x[0].airports), x[0].city))

    total = len(items)
    start = (max(page, 1) - 1) * page_size
    page_items = items[start : start + page_size]
    return {
        "origin": origin_airport.to_dict() if origin_airport else None,
        "total": total,
        "page": page,
        "page_size": page_size,
        "regions": regions(),
        "themes": list(THEMES),
        "themes_note": "Themes are an editorial classification for popular destinations.",
        "route_note": "“Seen in searches” means a flight search on FlyCompare returned offers for this route. Other destinations are suggestions; availability is not checked until you search.",
        "items": [
            {
                "key": c.key, "city": c.city, "country": c.country, "country_code": c.country_code, "region": c.region,
                "lat": c.lat, "lon": c.lon, "airport": c.primary.code,
                "airports": [{"code": a.code, "name": a.name} for a in c.airports],
                "themes": list(tags), "curated": bool(tags),
                "distance_km": round(d) if d is not None else None,
                "availability": seen[0] if seen else {"status": "suggestion"},
            }
            for c, tags, d, seen in page_items
        ],
        "generated_at": datetime.now(timezone.utc),
    }


def route_hubs(db: Session, origin: str, destination: str) -> list[dict]:
    """Connection airports seen in stored offers for a route, most frequent first."""
    rows = db.scalars(
        select(FareObservation.connections).where(
            FareObservation.origin_code == origin, FareObservation.destination_code == destination, FareObservation.connections.is_not(None)
        )
    ).all()
    counts: dict[str, int] = defaultdict(int)
    for value in rows:
        for code in filter(None, (value or "").split(",")):
            counts[code] += 1
    hubs = []
    for code, n in sorted(counts.items(), key=lambda kv: -kv[1])[:6]:
        a = get_airport(code)
        if a:
            hubs.append(a.to_dict(offers=n))
    return hubs
