"""Freely licensed photos for travel cards (sights, car models, vehicles, stays).

Reuses the Wikimedia plumbing from ``image_service`` (licence filtering,
attribution, rate-limit handling):

- ``article``: the lead image of the best-matching English Wikipedia article,
  found with a search so "Toyota Yaris" or "Hagia Sophia Istanbul" resolve even
  when the wording is not an exact title. Used for sights, car models and vehicles.
- ``stay``: a pool of Wikimedia Commons photos for a property type (hotel room,
  resort pool, apartment…) from which each property gets one deterministically.
  These are illustrative photos of the property type, never of a specific
  property, and the frontend labels them that way.

Every photo carries its author, licence and file page for the credit line.
Results are cached in memory; temporary failures are not cached.
"""

import re
import threading
import time
from hashlib import sha256

import httpx

from app.core.config import get_settings
from app.services import image_service
from app.services.image_service import WIKI_API, Unavailable

STAY_QUERIES = {
    "hotel": "hotel room bed interior",
    "resort": "resort swimming pool",
    "apartment": "apartment living room interior",
    "villa": "villa private swimming pool",
    "hostel": "hostel dormitory bunk beds",
}
NOT_A_PHOTO = re.compile(r"\b(map|logo|plan|diagram|floor ?plan|sign|menu|poster|stamp|coat of arms|drawing|sketch|advert)\b", re.IGNORECASE)
OK_SECONDS = 14 * 24 * 3600
NONE_SECONDS = 24 * 3600

_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _cached(key: str, loader):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now < hit[0]:
            return hit[1]
    value = loader()  # Unavailable propagates and is not cached
    with _lock:
        _cache[key] = (now + (OK_SECONDS if value else NONE_SECONDS), value)
    return value


def _client() -> httpx.Client:
    return httpx.Client(timeout=image_service.TIMEOUT, headers={"User-Agent": get_settings().wikimedia_user_agent}, follow_redirects=True)


def _article_photo(query: str) -> dict | None:
    with _client() as client:
        data = image_service._get_json(client, WIKI_API, {
            "action": "query", "format": "json", "formatversion": "2", "generator": "search", "gsrsearch": query,
            "gsrlimit": "3", "gsrnamespace": "0", "prop": "pageimages|info", "piprop": "name", "pilicense": "free", "inprop": "url",
        })
        pages = sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
        for page in pages:
            name = page.get("pageimage")
            if not name:
                continue
            photo = image_service._file_info(client, [name]).get(name.replace("_", " "))
            if photo:
                return {**photo, "source": "Wikipedia", "page_url": page.get("fullurl"), "subject": page.get("title")}
    return None


def _stay_pool(kind: str) -> list[dict]:
    query = STAY_QUERIES.get(kind, STAY_QUERIES["hotel"])
    with _client() as client:
        names = [n for n in image_service._search_commons(client, f"{query} filetype:bitmap", limit=30) if not NOT_A_PHOTO.search(n)]
        infos = image_service._file_info(client, names[:24])
    return [{**p, "source": "Wikimedia Commons", "page_url": None} for p in (infos.get(n.replace("_", " ")) for n in names[:24]) if p]


def photo(kind: str, query: str, seed: str = "", context: str = "") -> dict:
    """{"available": True, url, url_2x, artist, licence, file_url, source, illustrative} or {"available": False}.

    ``context`` (e.g. the city) is tried with the query first, then the query alone, so
    "Desert safari" still finds a photo when "Desert safari Dubai" has no article image.
    """
    if kind == "article" and context:
        with_context = photo(kind, f"{query} {context}", seed)
        if with_context.get("available") or with_context.get("pending"):
            return with_context
    if not get_settings().travel_external_data_enabled or not get_settings().destination_images_enabled:
        return {"available": False}
    q = re.sub(r"\s+or similar$", "", query.strip(), flags=re.IGNORECASE)[:120]
    if not q:
        return {"available": False}
    try:
        if kind == "stay":
            pool = _cached(f"pool:{q}", lambda: _stay_pool(q)) or []
            if not pool:
                return {"available": False}
            pick = pool[int(sha256(seed.encode()).hexdigest()[:8], 16) % len(pool)]
            return {"available": True, "illustrative": True, **pick}
        found = _cached(f"article:{q.lower()}", lambda: _article_photo(q))
        return {"available": True, "illustrative": False, **found} if found else {"available": False}
    except Unavailable:
        return {"available": False, "pending": True}
