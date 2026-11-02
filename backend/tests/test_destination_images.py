"""Destination photo lookup: sources, licence/relevance checks and caching. No network access."""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import init_db
from app.models import DestinationImage
from app.services import image_service


@dataclass(frozen=True)
class Place:
    key: str
    city: str
    country: str
    lat: float
    lon: float


KARACHI = Place("Karachi|PK", "Karachi", "Pakistan", 24.9, 67.16)
NASSAU = Place("Nassau|BS", "Nassau", "Bahamas", 25.04, -77.47)
SMALLTOWN = Place("Smalltown|XX", "Smalltown", "Nowhere", 10.0, 10.0)


def imageinfo(name, licence="CC BY-SA 4.0", mime="image/jpeg", width=2000, height=1200, artist="<a>Jane Doe</a>"):
    stem = name.replace(" ", "_")
    return {
        "title": f"File:{name}",
        "imageinfo": [{
            "thumburl": f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/{stem}/500px-{stem}?utm_source=x",
            "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{stem}",
            "mime": mime, "width": width, "height": height,
            "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": artist}},
        }],
    }


class FakeWikimedia:
    """Routes MediaWiki/REST calls to canned data and records every request."""

    def __init__(self, articles=None, files=None, search=None, missing_thumbs=(), status=200):
        self.articles, self.files, self.search = articles or {}, files or {}, search or {}
        self.missing_thumbs, self.status, self.calls = set(missing_thumbs), status, []

    def _response(self, payload, status=None):
        return httpx.Response(status or self.status, json=payload, request=httpx.Request("GET", "https://x"))

    def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if self.status != 200:
            return self._response({}, self.status)
        params = params or {}
        if "list" in params:  # Commons action API search
            hits = next((v for k, v in self.search.items() if k in params["srsearch"]), [])
            return self._response({"query": {"search": [{"title": f"File:{h}"} for h in hits]}})
        if params.get("prop", "").startswith("pageimages"):
            pages = [self.articles[t] for t in params["titles"].split("|") if t in self.articles]
            return self._response({"query": {"pages": pages}})
        if params.get("prop") == "imageinfo":
            pages = [self.files.get(t[5:], {"title": t, "missing": True}) for t in params["titles"].split("|")]
            return self._response({"query": {"pages": pages}})
        raise AssertionError(f"unexpected request {url} {params}")

    def head(self, url):
        self.calls.append((url, {}))
        missing = any(m.replace(" ", "_") in url for m in self.missing_thumbs)
        return httpx.Response(404 if missing else 200, headers={"content-type": "image/jpeg"})


def article(title, image, lat, lon, **extra):
    return {"title": title, "pageimage": image, "coordinates": [{"lat": lat, "lon": lon, "globe": "earth"}],
            "fullurl": f"https://en.wikipedia.org/wiki/{title}", **extra}


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    image_service._paused_until.clear()
    image_service._commons_direct_down_until = 0.0
    yield
    image_service._paused_until.clear()


# ------------------------------------------------------------------ licences and relevance

@pytest.mark.parametrize("raw, expected", [
    ("CC BY-SA 4.0", "CC BY-SA 4.0"),
    ("CC-BY-2.0", "CC BY 2.0"),  # hyphenated form used by local Wikipedia files
    ("CC BY-SA 3.0 de", "CC BY-SA 3.0 de"),
    ("CC0", "CC0"),
    ("Public domain", "Public domain"),
    ("PD-US", "Public domain"),
    ("CC BY-NC 2.0", None),
    ("CC BY-ND 4.0", None),
    ("All rights reserved", None),
    ("Fair use", None),
    (None, None),
])
def test_only_free_licences_are_accepted(raw, expected):
    assert image_service.normalise_licence(raw) == expected


@pytest.mark.parametrize("name, ok", [
    ("Karachi skyline at dusk.jpg", True),
    ("Downtown San José City (Costa Rica).jpg", True),
    ("SanSalvador_map.jpg", False),
    ("Flag of Karachi.jpg", False),
    ("Grey heron in a pond of Karachi park.jpg", False),
    ("Lahore Fort.jpg", False),  # does not name the city
])
def test_commons_file_names_must_name_the_city_and_look_like_a_view(name, ok):
    assert image_service.plausible_view(name, "Karachi" if "San" not in name else "San Jose") is ok


# ------------------------------------------------------------------ lookup sources

def test_wikipedia_lead_image_is_used_with_attribution():
    fake = FakeWikimedia(
        articles={"Karachi, Pakistan": article("Karachi", "Clifton_Karachi_View.jpg", 24.86, 67.01)},
        files={"Clifton Karachi View.jpg": imageinfo("Clifton Karachi View.jpg", licence="CC0")},
    )
    result = image_service.lookup(fake, [KARACHI])["Karachi|PK"]
    assert result["status"] == "ok" and result["source"] == "Wikipedia"
    assert result["licence"] == "CC0" and result["artist"] == "Jane Doe"
    assert result["url"].endswith("/500px-Clifton_Karachi_View.jpg")  # query string stripped
    assert result["url_2x"].endswith("/960px-Clifton_Karachi_View.jpg")
    assert result["page_url"] == "https://en.wikipedia.org/wiki/Karachi"
    assert result["file_url"].startswith("https://commons.wikimedia.org/wiki/File:")


def test_article_far_from_the_destination_is_ignored_and_commons_is_searched():
    # "Nassau" resolves to an article about a town in Germany: coordinates don't match the Bahamas.
    fake = FakeWikimedia(
        articles={"Nassau": article("Nassau, Germany", "Nassau_Burg.jpg", 50.3, 7.8)},
        files={"Nassau Burg.jpg": imageinfo("Nassau Burg.jpg"), "Nassau harbour panorama.jpg": imageinfo("Nassau harbour panorama.jpg")},
        search={'intitle:"Nassau" "Bahamas"': ["Nassau harbour panorama.jpg"]},
    )
    result = image_service.lookup(fake, [NASSAU])["Nassau|BS"]
    assert result["source"] == "Wikimedia Commons" and "Nassau_harbour_panorama" in result["url"]
    assert result["page_url"] is None


def test_unsuitable_lead_images_fall_back_to_commons():
    fake = FakeWikimedia(
        articles={"Karachi": article("Karachi", "Flag_of_Karachi.svg", 24.86, 67.01)},
        files={
            "Karachi port aerial view.jpg": imageinfo("Karachi port aerial view.jpg", licence="All rights reserved"),
            "Karachi skyline.jpg": imageinfo("Karachi skyline.jpg"),
            "Karachi skyline 2.jpg": imageinfo("Karachi skyline 2.jpg", mime="image/png"),
        },
        search={'intitle:"Karachi" "Pakistan" (': ["Karachi skyline 2.jpg", "Karachi port aerial view.jpg", "Karachi skyline.jpg"]},
    )
    result = image_service.lookup(fake, [KARACHI])["Karachi|PK"]
    assert result["source"] == "Wikimedia Commons" and result["url"].endswith("500px-Karachi_skyline.jpg")
    # The flag never reached the licence lookup.
    assert not any("Flag_of_Karachi" in str(params) or "Flag of Karachi" in str(params) for _, params in fake.calls)


def test_unreachable_thumbnail_is_skipped():
    fake = FakeWikimedia(
        articles={"Karachi": article("Karachi", "Karachi_view.jpg", 24.86, 67.01)},
        files={"Karachi view.jpg": imageinfo("Karachi view.jpg")},
        missing_thumbs={"Karachi view.jpg"},
    )
    assert image_service.lookup(fake, [KARACHI]) == {"Karachi|PK": {"status": "none"}}


def test_no_suitable_photo_anywhere_is_a_definite_none():
    fake = FakeWikimedia()
    assert image_service.lookup(fake, [SMALLTOWN]) == {"Smalltown|XX": {"status": "none"}}
    # Two Commons searches at most.
    assert len([c for c in fake.calls if "list" in c[1]]) == 2


def test_wikipedia_lookups_are_batched():
    places = [Place(f"City{i}|XX", f"City{i}", "Nowhere", 0, 0) for i in range(30)]  # 60 titles
    fake = FakeWikimedia()
    image_service.lookup(fake, places, commons_limit=0)
    assert len([c for c in fake.calls if c[1].get("prop", "").startswith("pageimages")]) == 2


def test_commons_searches_are_bounded_per_call():
    places = [Place(f"City{i}|XX", f"City{i}", "Nowhere", 0, 0) for i in range(5)]
    result = image_service.lookup(FakeWikimedia(), places, commons_limit=2)
    assert len(result) == 2  # the other three are left for a later call


def test_rate_limiting_raises_unavailable_and_pauses_the_host(monkeypatch):
    monkeypatch.setattr(image_service.time, "sleep", lambda _s: None)
    fake = FakeWikimedia(status=429)
    with pytest.raises(image_service.Unavailable):
        image_service.lookup(fake, [KARACHI])
    calls = len(fake.calls)
    with pytest.raises(image_service.Unavailable):
        image_service.lookup(fake, [KARACHI])
    assert len(fake.calls) == calls  # paused: no further requests


def test_refused_user_agent_is_unavailable_not_none():
    with pytest.raises(image_service.Unavailable):
        image_service.lookup(FakeWikimedia(status=403), [KARACHI])


def test_commons_rest_mirror_is_used_when_commons_is_unreachable():
    class Blocked(FakeWikimedia):
        def get(self, url, params=None):
            if url == image_service.COMMONS_API:
                raise httpx.ConnectError("reset")
            if url == image_service.COMMONS_SEARCH_REST:
                self.calls.append((url, dict(params)))
                return self._response({"pages": [{"title": "File:Karachi skyline.jpg"}]})
            return super().get(url, params)

    fake = Blocked(files={"Karachi skyline.jpg": imageinfo("Karachi skyline.jpg")})
    assert image_service.lookup(fake, [KARACHI])["Karachi|PK"]["source"] == "Wikimedia Commons"


# ------------------------------------------------------------------ cache

OK = {"status": "ok", "source": "Wikipedia", "url": "https://upload.wikimedia.org/x/500px-Dubai.jpg", "url_2x": None,
      "page_url": "https://en.wikipedia.org/wiki/Dubai", "file_url": "https://commons.wikimedia.org/wiki/File:Dubai.jpg",
      "licence": "CC BY-SA 4.0", "artist": "Someone"}


def test_endpoint_caches_hits_and_misses_but_not_pending(client, db_session, monkeypatch):
    calls = []

    def fake_lookup(_client, places):
        calls.append([p.key for p in places])
        return {k: v for k, v in {"Dubai|AE": OK, "Karachi|PK": {"status": "none"}}.items() if k in [p.key for p in places]}

    monkeypatch.setattr(image_service, "lookup", fake_lookup)
    data = client.get("/api/destinations/images?keys=Dubai|AE,Karachi|PK,Lahore|PK,Nowhere|XX").json()
    assert [d["key"] for d in data] == ["Dubai|AE", "Karachi|PK", "Lahore|PK"]  # unknown keys ignored
    assert data[0]["available"] is True and data[0]["source"] == "Wikipedia" and data[0]["retrieved_at"]
    assert data[1] == {"key": "Karachi|PK", "available": False}
    assert data[2] == {"key": "Lahore|PK", "available": False, "pending": True}

    client.get("/api/destinations/images?keys=Dubai|AE,Karachi|PK,Lahore|PK")
    assert calls[1] == ["Lahore|PK"]  # hit and miss served from cache; pending retried
    assert {r.key for r in db_session.scalars(select(DestinationImage))} == {"Dubai|AE", "Karachi|PK"}


def test_negative_results_expire_sooner_than_photos(db_session, monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(days=image_service.NONE_DAYS + 1)
    db_session.add_all([
        DestinationImage(key="Dubai|AE", status="ok", url="https://x/a.jpg", licence="CC0", artist="A", fetched_at=old),
        DestinationImage(key="Karachi|PK", status="none", fetched_at=old),
    ])
    db_session.commit()
    seen = []
    places = [Place("Dubai|AE", "Dubai", "United Arab Emirates", 25.2, 55.3), KARACHI]
    image_service.images_for(db_session, places, finder=lambda _c, ps: seen.extend(p.key for p in ps) or {})
    assert seen == ["Karachi|PK"]


def test_failed_lookup_keeps_previous_photo(db_session):
    old = datetime.now(timezone.utc) - timedelta(days=image_service.OK_DAYS + 1)
    db_session.add(DestinationImage(key="Karachi|PK", status="ok", url="https://x/a.jpg", licence="CC0", artist="A", fetched_at=old))
    db_session.commit()

    def unavailable(_c, _p):
        raise image_service.Unavailable("offline")

    assert image_service.images_for(db_session, [KARACHI], finder=unavailable)[0]["available"] is True
    assert image_service.images_for(db_session, [KARACHI], finder=lambda _c, _p: {"Karachi|PK": {"status": "none"}})[0]["url"] == "https://x/a.jpg"


def test_concurrent_requests_look_up_each_city_once(tmp_path):
    # A file database with a connection per thread (the shared in-memory test DB is single-connection).
    engine = create_engine(f"sqlite:///{tmp_path / 'images.db'}", connect_args={"check_same_thread": False})
    init_db(engine)
    sessions = sessionmaker(bind=engine)
    calls = []

    def slow_lookup(_client, places):
        calls.append([p.key for p in places])
        time.sleep(0.3)
        return {p.key: {"status": "none"} for p in places}

    results = []

    def worker():
        with sessions() as db:
            results.append(image_service.images_for(db, [KARACHI], finder=slow_lookup))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == [["Karachi|PK"]]
    assert len(results) == 3 and all(r == [{"key": "Karachi|PK", "available": False}] for r in results)
    engine.dispose()
