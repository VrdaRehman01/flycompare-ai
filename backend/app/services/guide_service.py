"""Travel guides: editorial city content plus real climate and an encyclopaedia summary.

- Climate: a full calendar year of daily observations from the Open-Meteo
  historical weather API (free, no key, CC BY 4.0), aggregated per month. It is
  one year of real data, labelled with that year, not a 30-year normal.
- "Best months" are ranked from that climate: comfortable daytime highs and few
  rainy days score best.
- Overview: the Wikipedia page summary (CC BY-SA), linked to the article.
Both are cached in memory and skipped entirely when external data is disabled.
"""

import threading
import time
from datetime import date

import httpx

from app.core.config import get_settings
from app.data.travel_content import GUIDES
from app.services.destination_service import City
from app.services.travel_common import city_summary, cost_index, guide_for, resolve_city

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WIKI_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
CACHE_SECONDS = 7 * 24 * 3600

_cache: dict[str, tuple[float, dict | None]] = {}
_lock = threading.Lock()


def _cached(key: str, loader):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    value = loader()
    if value is not None:  # failures are retried on the next request rather than cached
        with _lock:
            _cache[key] = (now, value)
    return value


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def month_score(high: float | None, rainy_days: float | None) -> float:
    """0–1 comfort score: daytime highs near 24°C and few rainy days are best."""
    if high is None:
        return 0.0
    temp = max(0.0, 1 - abs(high - 24) / 14)
    rain = 1 - min(1.0, (rainy_days or 0) / 18)
    return round(0.65 * temp + 0.35 * rain, 3)


def aggregate_climate(daily: dict, year: int) -> dict | None:
    times = daily.get("time") or []
    highs, lows, precip = daily.get("temperature_2m_max") or [], daily.get("temperature_2m_min") or [], daily.get("precipitation_sum") or []
    buckets: dict[int, dict[str, list[float]]] = {m: {"hi": [], "lo": [], "p": []} for m in range(1, 13)}
    for i, day in enumerate(times):
        m = int(day[5:7])
        if i < len(highs) and highs[i] is not None:
            buckets[m]["hi"].append(highs[i])
        if i < len(lows) and lows[i] is not None:
            buckets[m]["lo"].append(lows[i])
        if i < len(precip) and precip[i] is not None:
            buckets[m]["p"].append(precip[i])
    months = []
    for m in range(1, 13):
        b = buckets[m]
        if not b["hi"]:
            return None
        high = round(sum(b["hi"]) / len(b["hi"]), 1)
        rainy = sum(1 for p in b["p"] if p >= 1.0)
        months.append({
            "month": m, "name": MONTHS[m - 1], "avg_high_c": high,
            "avg_low_c": round(sum(b["lo"]) / len(b["lo"]), 1) if b["lo"] else None,
            "precip_mm": round(sum(b["p"]), 0), "rainy_days": rainy, "score": month_score(high, rainy),
        })
    ranked = sorted(months, key=lambda x: -x["score"])
    return {
        "year": year, "months": months,
        "best_months": [x["name"] for x in ranked[:3]],
        "avoid_months": [x["name"] for x in ranked[-2:] if x["score"] < 0.45],
        "source": f"Open-Meteo historical weather, {year} daily observations (CC BY 4.0)",
    }


def climate(city: City) -> dict | None:
    settings = get_settings()
    if not settings.travel_external_data_enabled:
        return None
    year = date.today().year - 1

    def load():
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(ARCHIVE_URL, params={
                    "latitude": f"{city.lat:.4f}", "longitude": f"{city.lon:.4f}", "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum", "timezone": "auto",
                })
            if r.status_code != 200:
                return None
            return aggregate_climate(r.json().get("daily") or {}, year)
        except (httpx.HTTPError, ValueError):
            return None

    return _cached(f"climate:{city.key}:{year}", load)


def wiki_summary(title: str) -> dict | None:
    settings = get_settings()
    if not settings.travel_external_data_enabled:
        return None

    def load():
        try:
            with httpx.Client(timeout=8.0, headers={"User-Agent": settings.wikimedia_user_agent}) as client:
                r = client.get(WIKI_URL.format(title=title.replace(" ", "_")))
            if r.status_code != 200:
                return None
            data = r.json()
            if data.get("type") == "disambiguation" or not data.get("extract"):
                return None
            return {
                "title": data.get("title"), "extract": data.get("extract"),
                "url": (data.get("content_urls") or {}).get("desktop", {}).get("page"),
                "source": "Wikipedia (CC BY-SA 4.0)",
            }
        except (httpx.HTTPError, ValueError):
            return None

    return _cached(f"wiki:{title}", load)


def list_guides() -> list[dict]:
    out = []
    for key, g in GUIDES.items():
        try:
            city = resolve_city(key)
        except ValueError:
            continue
        cats: dict[str, int] = {}
        for s in g.sights:
            cats[s.category] = cats.get(s.category, 0) + 1
        out.append({
            **city_summary(city), "tagline": g.tagline,
            "top_categories": [c for c, _ in sorted(cats.items(), key=lambda kv: -kv[1])[:3]],
            "sights": len(g.sights),
        })
    return out


def guide_detail(location: str) -> dict:
    city = resolve_city(location)
    g = guide_for(city)
    wiki = wiki_summary(g.wiki_title if g else city.city)
    return {
        **city_summary(city),
        "curated": bool(g),
        "tagline": g.tagline if g else None,
        "language": g.language if g else None,
        "currency": g.currency if g else None,
        "typical_hotel_night_usd": round(cost_index(city)),
        "areas": [a._asdict() for a in g.areas] if g else [],
        "sights": [s._asdict() for s in g.sights] if g else [],
        "tips": list(g.tips) if g else [],
        "overview": wiki,
        "climate": climate(city),
        "content_note": "Sights, areas and tips are editorial. Durations and admission prices are typical figures for planning; check before you go.",
    }
