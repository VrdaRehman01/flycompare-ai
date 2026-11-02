"""Global airport search backed by the bundled OurAirports-derived dataset.

The dataset (app/data/airports_global.json) contains ~4,000 airports with IATA
codes and scheduled passenger service. Search matches IATA/ICAO codes, metro
codes (LON, NYC, …), city, airport name, country and country aliases, and ranks
results so major airports of the matching city come first.
"""

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "airports_global.json"

COUNTRY_ALIASES = {
    "uk": "GB", "britain": "GB", "great britain": "GB", "england": "GB", "scotland": "GB", "usa": "US", "us": "US",
    "america": "US", "united states of america": "US", "uae": "AE", "emirates": "AE", "ksa": "SA", "saudi": "SA",
    "turkey": "TR", "turkiye": "TR", "holland": "NL", "korea": "KR", "south korea": "KR", "russia": "RU",
    "czech republic": "CZ", "vietnam": "VN", "laos": "LA", "iran": "IR", "syria": "SY",
}
CONTINENTS = {"AF": "Africa", "AN": "Antarctica", "AS": "Asia", "EU": "Europe", "NA": "North America", "OC": "Oceania", "SA": "South America"}
# Major passenger hubs in rough order of annual traffic (public airport-traffic
# rankings). Used only to order results, e.g. Heathrow before Gatwick.
HUBS = (
    "ATL DXB DFW LHR HND DEN IST LAX ORD DEL CDG JFK CAN AMS PVG SIN MAD ICN PEK FRA BKK SFO LAS CLT MCO MIA DOH SEA "
    "EWR PHX IAH BOM CGK KUL MEX MUC FCO BCN SYD NRT HKG TPE YYZ LGW SVO JED RUH AUH MNL SGN BOS DTW MSP GRU BLR "
    "MAA CCU HYD KHI LHE ISB DAC CMB KTM MLE MCT BAH KWI CAI ADD NBO JNB CPT LOS CMN TUN ALG SAW AYT ESB ADB ZRH "
    "VIE CPH ARN OSL HEL DUB LIS ATH WAW PRG BUD BRU DUS HAM BER TXL MXP LIN VCE NCE MAN EDI STN LTN LCY ORY "
    "LGA IAD DCA PHL BWI SAN PDX HNL YVR YUL GIG EZE SCL LIM BOG PTY KIX ITM FUK CTS GMP PUS SHA PKX SZX CTU KMG "
    "XIY HAK HKT DPS CNX DMK HAN DAD PNH RGN SZB CEB MEL BNE PER AKL CHC TLV AMM BEY BGW EBL SHJ DWC MED DMM"
).split()
HUB_BONUS = {code: 200 - i for i, code in enumerate(HUBS)}

MIDDLE_EAST = {"AE", "QA", "SA", "OM", "BH", "KW", "JO", "LB", "IL", "PS", "IQ", "IR", "SY", "YE", "EG"}


def fold(value: str) -> str:
    """Lower-case and strip accents so "Sao Paulo" matches "São Paulo"."""
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"\s+", " ", "".join(c for c in value if not unicodedata.combining(c))).strip().casefold()


def region_for(country_code: str, continent: str) -> str:
    return "Middle East" if country_code in MIDDLE_EAST else CONTINENTS.get(continent, continent)


@dataclass(frozen=True)
class Airport:
    code: str
    icao: str | None
    name: str
    city: str
    country: str
    country_code: str
    continent: str
    lat: float
    lon: float
    tz: str | None
    rank: int
    keywords: tuple[str, ...]
    f_city: str
    f_name: str
    f_country: str

    @property
    def region(self) -> str:
        return region_for(self.country_code, self.continent)

    def to_dict(self, **extra) -> dict:
        return {
            "code": self.code, "icao": self.icao, "name": self.name, "city": self.city, "country": self.country,
            "country_code": self.country_code, "region": self.region, "lat": self.lat, "lon": self.lon,
            "timezone": self.tz, "importance": self.rank, **extra,
        }


@dataclass(frozen=True)
class Dataset:
    airports: tuple[Airport, ...]
    by_code: dict[str, Airport]
    countries: dict[str, dict]
    source: str


@lru_cache(maxsize=1)
def dataset() -> Dataset:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    airports = []
    for a in raw["airports"]:
        keywords = tuple(k.strip() for k in (a.get("keywords") or "").split(",") if k.strip())
        airports.append(Airport(
            code=a["iata"], icao=a.get("icao"), name=a["name"], city=a["city"], country=a["country"],
            country_code=a["country_code"], continent=a["continent"], lat=a["lat"], lon=a["lon"], tz=a.get("tz"),
            rank=a["rank"], keywords=keywords, f_city=fold(a["city"]), f_name=fold(a["name"]), f_country=fold(a["country"]),
        ))
    airports_t = tuple(airports)
    return Dataset(airports_t, {a.code: a for a in airports_t}, raw["countries"], raw["source"])


@lru_cache(maxsize=1)
def metro_codes() -> dict[str, tuple[str, ...]]:
    """Metropolitan area codes (LON, NYC, TYO…) found in airport keywords."""
    out: dict[str, list[str]] = {}
    by_code = dataset().by_code
    for a in dataset().airports:
        for k in a.keywords:
            if len(k) == 3 and k.isupper() and k.isalpha() and k not in by_code and a.rank >= 2:
                out.setdefault(k, []).append(a.code)
    return {k: tuple(v) for k, v in out.items()}


def is_known_location(code: str) -> bool:
    code = code.upper()
    return code in dataset().by_code or code in metro_codes()


def get_airport(code: str) -> Airport | None:
    return dataset().by_code.get(code.strip().upper())


def city_for_code(code: str) -> str | None:
    airport = get_airport(code)
    return airport.city if airport else None


def _score(a: Airport, q: str, q_upper: str, country_code: str | None) -> int:
    score = 0
    if len(q_upper) == 3 and a.code == q_upper:
        score = 1000
    elif len(q_upper) == 4 and a.icao == q_upper:
        score = 900
    elif len(q_upper) == 3 and q_upper in a.keywords:
        score = 650  # metro/city code such as LON or NYC
    elif a.f_city == q:
        score = 600
    elif a.f_city.startswith(q):
        score = 450
    elif a.f_name.startswith(q) or any(w.startswith(q) for w in a.f_name.split()):
        score = 350
    elif country_code and a.country_code == country_code:
        score = 250
    elif len(q) >= 3 and q in a.f_city:
        score = 200
    elif len(q) >= 3 and q in a.f_name:
        score = 150
    elif len(q) >= 4 and any(q in fold(k) for k in a.keywords):
        score = 120
    if score:
        score += a.rank * 30 + HUB_BONUS.get(a.code, 0) // 4
    return score


def _country_match(q: str) -> str | None:
    if q in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[q]
    for code, info in dataset().countries.items():
        name = fold(info["name"])
        if name == q or (len(q) >= 4 and name.startswith(q)):
            return code
    return None


def search_airports(query: str, limit: int = 10) -> list[dict]:
    q = fold(query)
    if len(q) < 2:
        return []
    q_upper = query.strip().upper()
    country_code = _country_match(q)
    scored = []
    for a in dataset().airports:
        s = _score(a, q, q_upper, country_code)
        # Country-only matches return the country's main airports, not every airstrip.
        if s and not (country_code and a.country_code == country_code and s < 300 and a.rank < 3):
            scored.append((s, a))
    scored.sort(key=lambda x: (-x[0], -x[1].rank, -HUB_BONUS.get(x[1].code, 0), x[1].city, x[1].code))
    results = [a for _, a in scored[:limit]]
    # Keep airports of the same city together, ordered by the city's best match.
    order: dict[tuple[str, str], int] = {}
    for i, a in enumerate(results):
        order.setdefault((a.city, a.country_code), i)
    results.sort(key=lambda a: (order[(a.city, a.country_code)], -a.rank, -HUB_BONUS.get(a.code, 0)))
    return [a.to_dict() for a in results]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def nearby_airports(lat: float, lon: float, limit: int = 5, max_km: float = 250.0) -> list[dict]:
    """Closest commercial airports (large, or medium with scheduled service)."""
    found = []
    for a in dataset().airports:
        if a.rank < 2:
            continue
        d = haversine_km(lat, lon, a.lat, a.lon)
        if d <= max_km:
            found.append((d, a))
    # Prefer major airports when two are similarly close (within 40 km of each other).
    found.sort(key=lambda x: x[0] - (40 if x[1].rank == 3 else 0))
    return [a.to_dict(distance_km=round(d, 1)) for d, a in found[:limit]]


def airports_for_codes(codes: list[str]) -> list[dict]:
    return [a.to_dict() for c in codes if (a := get_airport(c))]
