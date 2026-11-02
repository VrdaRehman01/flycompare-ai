"""Destination photos from Wikipedia / Wikimedia Commons with attribution.

Lookup order for each city:

1. The lead image of the city's English Wikipedia article. Titles are tried as
   "City, Country", then "City" (redirects followed, disambiguation pages
   skipped). An article only counts when its coordinates lie within
   MAX_DISTANCE_KM of the destination, so e.g. San Salvador (Bahamas) never
   receives the photo of El Salvador's capital.
2. A Wikimedia Commons file search ("<city> skyline / cityscape / …"). The
   file title must name the city and must not look like a map, flag, logo,
   vehicle, portrait, etc.
3. Nothing: the frontend shows its built-in illustration.

Only free licences are accepted (CC0, CC BY, CC BY-SA, public domain) and the
author, licence and file page are stored so every photo can be credited.

Wikipedia lookups are batched (up to 50 titles per request), so the full
catalogue of ~1,100 cities costs a few dozen requests. Results are cached:
photos for OK_DAYS, "no suitable photo" for NONE_DAYS. Network errors, rate
limiting and refused requests are never cached; those cities are reported as
``pending`` and retried later.
"""

import html
import logging
import re
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DestinationImage
from app.services.airport_service import fold, haversine_km

logger = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# REST mirror of the Commons search, used when commons.wikimedia.org cannot be reached.
COMMONS_SEARCH_REST = "https://api.wikimedia.org/core/v1/commons/search/page"

OK_DAYS = 30
NONE_DAYS = 7
THUMB_WIDTH = 500  # Wikimedia serves standard thumbnail widths (330, 500, 960, …)
THUMB_WIDTH_2X = 960
MAX_DISTANCE_KM = 80  # destination coordinates come from its main airport
BATCH = 50  # MediaWiki limit for titles per query
COMMONS_PER_CALL = 8  # Commons searches per API call; other cities are left pending
WORKERS = 3
TIMEOUT = httpx.Timeout(8.0, connect=5.0)
MAX_RETRY_WAIT = 5.0
RATE_LIMIT_PAUSE = 60.0

SCENIC_QUERY = "(skyline OR cityscape OR panorama OR downtown OR aerial OR landmark)"
SCENIC_WORDS = re.compile(
    r"\b(skyline|cityscape|panorama|panoramic|downtown|centre|center|old town|aerial|drone|view|harbou?r|waterfront|"
    r"landmark|square|street|avenue|boulevard|bridge|beach|port|bay|river|mosque|cathedral|church|temple|palace|fort|"
    r"tower|market|promenade|city|town|skyscrapers?)\b",
    re.IGNORECASE,
)
NOT_A_VIEW = re.compile(
    r"\b(map|locator|flag|seal|logo|coat of arms|emblem|crest|diagram|chart|plan|stamp|coin|banknote|portrait|"
    r"signature|document|poster|sign|ticket|menu|bus|train|tram|metro|aircraft|airplane|airliner|plane|car|truck|"
    r"interior|team|match|people|girls?|boys?|children|women|men|animals?|birds?|heron|eagle|gull|duck|monitor|lizard|snake|butterfly|insect|dog|cat|horse|"
    r"fish|monkey|flower|plant|food|dish)\b",
    re.IGNORECASE,
)
PHOTO_MIME = {"image/jpeg", "image/webp"}


class Unavailable(Exception):
    """A temporary failure (network, rate limit, refused request). Never cached."""


class Place(Protocol):
    key: str
    city: str
    country: str
    lat: float
    lon: float


# Per-host pause after rate limiting, and whether commons.wikimedia.org is reachable.
_state_lock = threading.Lock()
_paused_until: dict[str, float] = {}
_commons_direct_down_until = 0.0


def _strip_html(value: str | None, limit: int = 200) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()
    doubled = re.fullmatch(r"(.+?)\s*\1", text)  # Commons sometimes repeats the author ("XX")
    return (doubled.group(1) if doubled else text)[:limit] or None


def _without_query(url: str) -> str:
    return url.split("?", 1)[0]


def normalise_licence(raw: str | None) -> str | None:
    """Return a display name for an allowed free licence, or None."""
    text = _strip_html(raw)
    if not text:
        return None
    norm = re.sub(r"[\s_-]+", " ", text).strip()
    m = re.fullmatch(r"CC BY( SA)?( \d\.\d)?( [a-z]{2,3})?", norm, re.IGNORECASE)
    if m:
        return f"CC BY{'-SA' if m.group(1) else ''}{m.group(2) or ''}{m.group(3) or ''}"
    if re.fullmatch(r"CC0( 1\.0)?", norm, re.IGNORECASE):
        return "CC0"
    if re.match(r"(public domain|PD\b)", norm, re.IGNORECASE):
        return "Public domain"
    return None


def _chunks(items: Sequence, size: int) -> Iterator[Sequence]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _retry_after(response: httpx.Response) -> float:
    try:
        return max(0.5, float(response.headers.get("retry-after", "1")))
    except ValueError:
        return 1.0


def _get_json(client: httpx.Client, url: str, params: dict) -> dict:
    host = urlsplit(url).netloc
    if time.monotonic() < _paused_until.get(host, 0.0):
        raise Unavailable(f"{host} is rate limiting")
    for attempt in range(2):
        try:
            response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise Unavailable(f"{host}: {exc.__class__.__name__}") from exc
        if response.status_code in (429, 503):
            wait = _retry_after(response)
            if attempt == 0 and wait <= MAX_RETRY_WAIT:
                time.sleep(wait)
                continue
            with _state_lock:
                _paused_until[host] = time.monotonic() + max(wait, RATE_LIMIT_PAUSE)
            raise Unavailable(f"{host} is rate limiting")
        if response.status_code == 403:
            logger.warning(
                "Wikimedia refused an image lookup (403). Set WIKIMEDIA_USER_AGENT to include a contact URL or "
                "email, as required by https://meta.wikimedia.org/wiki/User-Agent_policy"
            )
            raise Unavailable(f"{host} refused the request")
        if response.status_code != 200:
            raise Unavailable(f"{host}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise Unavailable(f"{host}: invalid JSON") from exc
    raise Unavailable(f"{host} is rate limiting")


def _resolver(query: dict) -> Callable[[str], str]:
    moves = {m["from"]: m["to"] for step in ("normalized", "redirects") for m in query.get(step, [])}

    def resolve(title: str) -> str:
        for _ in range(4):
            title = moves.get(title, title)
        return title

    return resolve


def _titles(place: Place) -> list[str]:
    titles = [f"{place.city}, {place.country}", place.city]
    ascii_city = fold(place.city)
    if ascii_city and ascii_city.lower() != place.city.lower():
        titles.append(ascii_city.title())
    return titles


def _articles(client: httpx.Client, places: Sequence[Place]) -> dict[str, dict]:
    """key -> {"title", "page_url", "image"} for cities with a matching Wikipedia article."""
    wanted: dict[str, list[tuple[Place, int]]] = {}
    for place in places:
        for priority, title in enumerate(_titles(place)):
            wanted.setdefault(title, []).append((place, priority))
    best: dict[str, tuple[int, dict]] = {}
    for chunk in _chunks(list(wanted), BATCH):
        data = _get_json(client, WIKI_API, {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "titles": "|".join(chunk), "prop": "pageimages|coordinates|pageprops|info",
            "piprop": "name", "pilicense": "free", "ppprop": "disambiguation", "colimit": "max", "inprop": "url",
        })
        query = data.get("query", {})
        resolve = _resolver(query)
        pages = {p["title"]: p for p in query.get("pages", [])}
        for title in chunk:
            page = pages.get(resolve(title))
            if not page or page.get("missing") or "disambiguation" in (page.get("pageprops") or {}):
                continue
            coords = next((c for c in page.get("coordinates") or [] if c.get("globe", "earth") == "earth"), None)
            for place, priority in wanted[title]:
                if not coords or haversine_km(place.lat, place.lon, coords["lat"], coords["lon"]) > MAX_DISTANCE_KM:
                    continue
                if place.key not in best or priority < best[place.key][0]:
                    best[place.key] = (priority, {
                        "title": page["title"],
                        "page_url": page.get("fullurl") or f"https://en.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}",
                        "image": page.get("pageimage"),
                    })
    return {key: article for key, (_, article) in best.items()}


def _photo(info: dict | None) -> dict | None:
    """Card-ready fields for a freely licensed photograph, or None if unsuitable."""
    if not info or not info.get("thumburl") or info.get("mime") not in PHOTO_MIME:
        return None
    width, height = info.get("width") or 0, info.get("height") or 0
    if width < 640 or not height or not 0.5 <= width / height <= 2.8:
        return None
    meta = info.get("extmetadata") or {}
    licence = normalise_licence((meta.get("LicenseShortName") or {}).get("value"))
    if not licence:
        return None
    url = _without_query(info["thumburl"])
    url_2x = re.sub(r"/\d+px-", f"/{THUMB_WIDTH_2X}px-", url, count=1) if width >= THUMB_WIDTH_2X and "px-" in url else None
    return {
        "url": url,
        "url_2x": url_2x,
        "file_url": info.get("descriptionurl"),
        "licence": licence,
        "artist": _strip_html((meta.get("Artist") or {}).get("value"))
        or _strip_html((meta.get("Credit") or {}).get("value"))
        or "Unknown author",
    }


def _file_info(client: httpx.Client, names: Sequence[str]) -> dict[str, dict | None]:
    """File name (without "File:") -> photo fields, or None when unsuitable."""
    out: dict[str, dict | None] = {}
    unique = list(dict.fromkeys(n.replace("_", " ") for n in names))
    for chunk in _chunks(unique, BATCH):
        data = _get_json(client, WIKI_API, {
            "action": "query", "format": "json", "formatversion": "2",
            "titles": "|".join(f"File:{name}" for name in chunk),
            "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": str(THUMB_WIDTH),
            "iiextmetadatafilter": "LicenseShortName|Artist|Credit",
        })
        query = data.get("query", {})
        resolve = _resolver(query)
        pages = {p["title"]: p for p in query.get("pages", [])}
        for name in chunk:
            page = pages.get(resolve(f"File:{name}")) or {}
            out[name] = _photo((page.get("imageinfo") or [None])[0])
    return out


def _reachable(client: httpx.Client, url: str) -> bool:
    """Confirm the thumbnail is served. Missing files return False; network trouble raises Unavailable."""
    try:
        response = client.head(url)
    except httpx.HTTPError as exc:
        raise Unavailable(f"thumbnail check failed: {exc.__class__.__name__}") from exc
    if response.status_code in (404, 410):
        return False
    if response.status_code >= 400:
        raise Unavailable(f"thumbnail check: HTTP {response.status_code}")
    return response.headers.get("content-type", "image/").startswith("image/")


def _search_commons(client: httpx.Client, query: str, limit: int = 12) -> list[str]:
    global _commons_direct_down_until
    if time.monotonic() >= _commons_direct_down_until:
        try:
            data = _get_json(client, COMMONS_API, {
                "action": "query", "format": "json", "formatversion": "2", "list": "search",
                "srsearch": query, "srnamespace": "6", "srlimit": str(limit),
            })
            return [r["title"].removeprefix("File:") for r in data.get("query", {}).get("search", [])]
        except Unavailable as exc:
            if not isinstance(exc.__cause__, httpx.TransportError):
                raise
            with _state_lock:
                _commons_direct_down_until = time.monotonic() + 3600
    data = _get_json(client, COMMONS_SEARCH_REST, {"q": query, "limit": str(limit)})
    return [p["title"].removeprefix("File:") for p in data.get("pages", []) if p.get("title", "").startswith("File:")]


def _commons_queries(place: Place) -> list[tuple[str, bool]]:
    """(search, needs a scenic word in the file title)."""
    city, country = place.city.replace('"', ""), place.country.replace('"', "")
    # The country is always part of the search: without it, a city name that is also a surname or a
    # place elsewhere ("Tahir", "Nassau") pulls in unrelated files.
    return [
        (f'intitle:"{city}" "{country}" {SCENIC_QUERY} filetype:bitmap', False),
        (f'intitle:"{city}" "{country}" filetype:bitmap', True),
    ]


def _stem(file_name: str) -> str:
    return re.sub(r"[_\-,()]+", " ", file_name.rsplit(".", 1)[0])


def plausible_view(file_name: str, city: str | None = None, needs_scenic: bool = False) -> bool:
    """Does a file name look like a view of a place (naming the city, when given) rather than a map, logo, animal…?"""
    stem = _stem(file_name)
    if NOT_A_VIEW.search(stem) or (city is not None and fold(city) not in fold(stem)):
        return False
    return not needs_scenic or bool(SCENIC_WORDS.search(stem))


def _from_commons(client: httpx.Client, place: Place) -> dict:
    tried: set[str] = set()
    for query, needs_scenic in _commons_queries(place):
        names = [n for n in _search_commons(client, query) if n not in tried and plausible_view(n, place.city, needs_scenic)]
        # Keep search order, but files whose title describes a view (skyline, old town, …) go first.
        names = sorted(names, key=lambda n: not SCENIC_WORDS.search(_stem(n)))[:6]
        tried.update(names)
        if not names:
            continue
        infos = _file_info(client, names)
        for name in names:
            photo = infos.get(name.replace("_", " "))
            if photo and _reachable(client, photo["url"]):
                return {"status": "ok", "source": "Wikimedia Commons", "page_url": None, **photo}
    return {"status": "none"}


def lookup(client: httpx.Client, places: Sequence[Place], commons_limit: int = COMMONS_PER_CALL) -> dict[str, dict]:
    """Find photos for several cities.

    Returns key -> {"status": "ok", …} or {"status": "none"} for every city that
    was checked conclusively. Cities missing from the result could not be
    checked right now (rate limit, network) or exceeded ``commons_limit``.
    """
    results: dict[str, dict] = {}
    articles = _articles(client, places)
    lead_images = [a["image"] for a in articles.values() if a.get("image") and plausible_view(a["image"])]
    infos = _file_info(client, lead_images)
    for place in places:
        article = articles.get(place.key)
        photo = infos.get(article["image"].replace("_", " ")) if article and article.get("image") else None
        if photo and _reachable(client, photo["url"]):
            results[place.key] = {"status": "ok", "source": "Wikipedia", "page_url": article["page_url"], **photo}

    def commons(place: Place) -> tuple[str, dict | None]:
        try:
            return place.key, _from_commons(client, place)
        except Unavailable as exc:
            logger.info("Commons lookup for %s postponed: %s", place.key, exc)
            return place.key, None

    remaining = [p for p in places if p.key not in results][:commons_limit]
    if remaining:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for key, result in pool.map(commons, remaining):
                if result is not None:
                    results[key] = result
    return results


# ---------------------------------------------------------------- cache

_inflight: dict[str, threading.Event] = {}
_inflight_lock = threading.Lock()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _expired(row: DestinationImage, now: datetime) -> bool:
    ttl = OK_DAYS if row.status == "ok" else NONE_DAYS
    return _aware(row.fetched_at) < now - timedelta(days=ttl)


def _row_out(row: DestinationImage) -> dict:
    if row.status != "ok":
        return {"key": row.key, "available": False}
    return {
        "key": row.key, "available": True, "url": row.url, "url_2x": row.url_2x, "licence": row.licence,
        "artist": _strip_html(row.artist) or row.artist, "file_url": row.file_url, "page_url": row.page_url,
        "source": row.source or "Wikipedia", "retrieved_at": _aware(row.fetched_at).isoformat(),
    }


def _store(db: Session, rows: dict[str, DestinationImage], found: dict[str, dict], now: datetime) -> None:
    for key, result in found.items():
        row = rows.get(key) or DestinationImage(key=key)
        if result["status"] != "ok" and row.status == "ok" and row.url:
            # Keep serving a previously verified photo rather than dropping it on a weaker lookup.
            row.fetched_at = now
        else:
            row.status = result["status"]
            for field in ("url", "url_2x", "page_url", "file_url", "licence", "artist", "source"):
                setattr(row, field, result.get(field))
            row.fetched_at = now
        db.add(row)
        rows[key] = row
    try:
        db.commit()
    except IntegrityError:  # another worker process stored the same key first
        db.rollback()


def images_for(db: Session, places: Sequence[Place], finder: Callable[..., dict[str, dict]] | None = None) -> list[dict]:
    """Cached photo info for each place. Uncached cities are looked up once, even under concurrent requests."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    keys = [p.key for p in places]
    rows = {r.key: r for r in db.scalars(select(DestinationImage).where(DestinationImage.key.in_(keys)))}
    stale = [p for p in places if p.key not in rows or _expired(rows[p.key], now)]
    if stale and settings.destination_images_enabled:
        with _inflight_lock:
            mine = [p for p in stale if p.key not in _inflight]
            waiting = [_inflight[p.key] for p in stale if p.key in _inflight]
            for p in mine:
                _inflight[p.key] = threading.Event()
        try:
            if mine:
                try:
                    headers = {"User-Agent": settings.wikimedia_user_agent, "Accept": "application/json"}
                    with httpx.Client(timeout=TIMEOUT, headers=headers, follow_redirects=True) as client:
                        found = (finder or lookup)(client, mine)
                except Unavailable as exc:
                    logger.info("Image lookup postponed for %d cities: %s", len(mine), exc)
                    found = {}
                _store(db, rows, found, now)
        finally:
            with _inflight_lock:
                for p in mine:
                    _inflight.pop(p.key).set()
        if waiting:
            for event in waiting:
                event.wait(timeout=20)
            db.expire_all()
            rows.update({r.key: r for r in db.scalars(select(DestinationImage).where(DestinationImage.key.in_(keys)))})
    pending = settings.destination_images_enabled
    return [_row_out(rows[k]) if k in rows else {"key": k, "available": False, "pending": pending} for k in keys]
