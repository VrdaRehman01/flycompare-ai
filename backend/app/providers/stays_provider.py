"""Accommodation search: Duffel Stays when available, otherwise labelled demo stays.

Duffel Stays (POST /stays/search) uses the same access token as flights but must
be enabled separately on the Duffel account. When it is not enabled, or fails,
the search falls back to deterministic demo properties with a notice, exactly as
flight search falls back to the demo provider. Demo properties use fictional
names placed in the city's real neighbourhoods; they are never stored.
"""

import math
from datetime import date

import httpx

from app.core.config import Settings
from app.services.airport_service import haversine_km
from app.services.destination_service import City
from app.services.travel_common import DEMO_NOTICE, centre, cost_index, guide_for, seeded

STAR_FACTOR = {2: 0.45, 3: 0.7, 4: 1.0, 5: 1.9}
NAME_WORDS = ("Harbour", "Palm", "Cedar", "Atlas", "Lantern", "Orchid", "Saffron", "Juniper", "Willow", "Azure", "Marble",
              "Linden", "Amber", "Coral", "Ivory", "Sandstone", "Silk Road", "Jasmine", "Olive", "Skyline")
DUFFEL_AMENITIES = {
    "wifi": "Free Wi-Fi", "pool": "Pool", "gym": "Gym", "spa": "Spa", "parking": "Parking", "restaurant": "Restaurant",
    "24_hour_front_desk": "24-hour front desk", "pets_allowed": "Pets allowed", "laundry": "Laundry", "lounge": "Lounge",
    "business_centre": "Business centre", "childcare_service": "Childcare", "accessibility_mobility": "Step-free access",
    "room_service": "Room service", "cash_machine": "ATM",
}


class StaysProviderError(Exception):
    pass


def _areas(city: City) -> list[tuple[str, str]]:
    guide = guide_for(city)
    if guide:
        return [(a.name, a.best_for) for a in guide.areas]
    return [("City Centre", "Sightseeing"), (f"Near {city.primary.name}", "Short stays and early flights"), ("Business District", "Business")]


def _middle(city: City) -> tuple[float, float]:
    """Search and measure from the city centre when known, else the dataset point (its airport)."""
    return centre(city) or (city.lat, city.lon)


def _offset(lat: float, lon: float, km: float, bearing_deg: float) -> tuple[float, float]:
    b = math.radians(bearing_deg)
    dlat = (km / 111.0) * math.cos(b)
    dlon = (km / (111.0 * max(math.cos(math.radians(lat)), 0.2))) * math.sin(b)
    return round(lat + dlat, 5), round(lon + dlon, 5)


class DemoStaysProvider:
    name = "FlyCompare Demo Stays"
    data_status = "demo"

    def search(self, city: City, check_in: date, check_out: date, adults: int, children: int, rooms: int) -> list[dict]:
        nights = (check_out - check_in).days
        rng = seeded("stays", city.key, check_in, check_out)
        index = cost_index(city)
        areas = _areas(city)
        guide = guide_for(city)
        beachy = any(s.category == "Beach" for s in guide.sights) if guide else False
        season = 0.9 + 0.3 * rng.random()
        weekend_nights = sum(1 for i in range(nights) if date.fromordinal(check_in.toordinal() + i).weekday() in (4, 5))
        weekend = 1 + 0.08 * weekend_nights / max(nights, 1)
        guests_per_room = (adults + children) / rooms
        crowding = 1 + max(0.0, guests_per_room - 2) * 0.15

        kinds = ["hotel"] * 11 + ["apartment"] * 4 + ["hostel"] * 2 + (["resort"] * 2 if beachy else ["hotel"]) + (["villa"] if beachy else [])
        words = rng.sample(NAME_WORDS, len(kinds))
        out = []
        for i, (kind, word) in enumerate(zip(kinds, words)):
            area_i = i % len(areas)
            area, best_for = areas[area_i]
            short_area = area.split(" (")[0].split(" & ")[0]
            if kind == "hotel":
                stars = rng.choice([3, 3, 4, 4, 4, 5, 5, 2])
                name = rng.choice([f"{word} {short_area} Hotel", f"The {word} {short_area}", f"{short_area} {word} Suites"])
                factor = STAR_FACTOR[stars]
            elif kind == "resort":
                stars = rng.choice([4, 5])
                name = f"{word} Bay Resort & Spa"
                factor = STAR_FACTOR[stars] * 1.15
            elif kind == "apartment":
                stars = None
                name = rng.choice([f"{word} Residences {short_area}", f"{short_area} {word} Apartments", f"{word} Serviced Lofts"])
                factor = 0.85
            elif kind == "villa":
                stars = None
                name = f"Villa {word}"
                factor = 2.2
            else:
                stars = None
                name = f"{word} Hostel {city.city}"
                factor = 0.22
            nightly = index * factor * season * weekend * crowding * (0.88 + 0.24 * rng.random())
            if kind not in ("apartment", "villa"):
                nightly *= rooms
            nightly = round(nightly, 0)
            km = round([0.4, 2.5, 4.0][min(area_i, 2)] + rng.random() * 2.5, 1)
            lat, lon = _offset(*_middle(city), km, rng.random() * 360)
            amenities = ["Free Wi-Fi", "Air conditioning"]
            if kind in ("hotel", "resort"):
                amenities += ["24-hour front desk"]
                if (stars or 0) >= 4 or kind == "resort":
                    amenities += ["Pool", "Gym", "Restaurant"]
                if (stars or 0) >= 5 or kind == "resort":
                    amenities += ["Spa", "Room service"]
                if rng.random() < 0.5:
                    amenities.append("Airport shuttle")
            if kind in ("apartment", "villa"):
                amenities += ["Kitchen", "Washing machine", "Self check-in"]
                if kind == "villa":
                    amenities += ["Private pool", "Garden"]
            if kind == "hostel":
                amenities += ["Shared lounge", "Lockers"]
            if rng.random() < 0.55:
                amenities.append("Parking")
            score_base = {None: 8.2, 2: 7.2, 3: 7.8, 4: 8.4, 5: 8.9}[stars]
            out.append({
                "id": f"demo-{seeded(city.key, name).randrange(16**10):010x}",
                "name": name,
                "property_type": kind,
                "stars": stars,
                "review_score": round(min(9.8, score_base + rng.uniform(-0.7, 0.8)), 1),
                "review_count": int(40 + rng.random() ** 2 * 3800),
                "area": area,
                "area_best_for": best_for,
                "address": f"{area}, {city.city}",
                "lat": lat,
                "lon": lon,
                "distance_km": km,
                "photo_url": None,
                "amenities": amenities,
                "free_cancellation": rng.random() < 0.6,
                "breakfast_included": kind in ("hotel", "resort") and rng.random() < 0.45,
                "nightly_price": nightly,
                "total_price": round(nightly * nights, 0),
                "currency": "USD",
                "rooms_left": rng.choice([None, None, None, 2, 3, 5]),
                "sleeps": {"apartment": 4, "villa": 6}.get(kind),
            })
        return out


class DuffelStaysProvider:
    name = "Duffel Stays"

    def __init__(self, settings: Settings):
        token = (settings.duffel_access_token or "").strip()
        if not token:
            raise StaysProviderError("No Duffel access token is configured.")
        self.token = token
        self.base_url = settings.duffel_api_url.rstrip("/")
        self.api_version = settings.duffel_api_version
        self.timeout = min(settings.duffel_timeout_seconds, 30.0)
        self.data_status = "test" if token.startswith("duffel_test_") else "live"

    def search(self, city: City, check_in: date, check_out: date, adults: int, children: int, rooms: int, child_ages: list[int] | None = None) -> list[dict]:
        ages = (child_ages or [])[:children] + [8] * max(0, children - len(child_ages or []))
        payload = {"data": {
            "rooms": rooms,
            "location": {"radius": 10, "geographic_coordinates": dict(zip(("latitude", "longitude"), _middle(city)))},
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guests": [{"type": "adult"}] * adults + [{"type": "child", "age": a} for a in ages],
        }}
        headers = {"Authorization": f"Bearer {self.token}", "Duffel-Version": self.api_version, "Accept": "application/json", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/stays/search", headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise StaysProviderError("Could not reach Duffel Stays.") from exc
        if response.status_code in (401, 403):
            raise StaysProviderError("Duffel Stays is not enabled for this Duffel account.")
        if response.status_code >= 400:
            raise StaysProviderError(f"Duffel Stays returned HTTP {response.status_code}.")
        try:
            results = response.json().get("data", {}).get("results", [])
        except ValueError as exc:
            raise StaysProviderError("Duffel Stays returned an unexpected response.") from exc
        nights = (check_out - check_in).days
        return [r for r in (self._map(item, city, nights) for item in results) if r]

    @staticmethod
    def _map(item: dict, city: City, nights: int) -> dict | None:
        acc = item.get("accommodation") or {}
        try:
            total = float(item.get("cheapest_rate_total_amount"))
        except (TypeError, ValueError):
            return None
        loc = acc.get("location") or {}
        coords = loc.get("geographic_coordinates") or {}
        address = loc.get("address") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        photos = acc.get("photos") or []
        amenities = [DUFFEL_AMENITIES.get(a.get("type"), a.get("description")) for a in acc.get("amenities") or [] if isinstance(a, dict)]
        rating = acc.get("rating")
        return {
            "id": item.get("id") or acc.get("id"),
            "name": acc.get("name") or "Unnamed property",
            "property_type": "hotel",
            "stars": int(rating) if isinstance(rating, (int, float)) else None,
            "review_score": acc.get("review_score"),
            "review_count": None,
            "area": address.get("city_name") or city.city,
            "area_best_for": None,
            "address": ", ".join(p for p in (address.get("line_one"), address.get("city_name")) if p),
            "lat": lat,
            "lon": lon,
            "distance_km": round(haversine_km(*_middle(city), lat, lon), 1) if lat is not None and lon is not None else None,
            "photo_url": photos[0].get("url") if photos and isinstance(photos[0], dict) else None,
            "amenities": [a for a in amenities if a],
            "free_cancellation": None,
            "breakfast_included": None,
            "nightly_price": round(total / max(nights, 1), 2),
            "total_price": total,
            "currency": item.get("cheapest_rate_currency") or "USD",
            "rooms_left": None,
            "sleeps": None,
        }


def search_stays(settings: Settings, city: City, check_in: date, check_out: date, adults: int, children: int, rooms: int, child_ages: list[int] | None = None) -> dict:
    """Run the configured stays search; fall back to demo stays with a notice if Duffel is unavailable."""
    mode = settings.stays_provider.strip().lower()
    use_duffel = mode == "duffel" or (mode == "auto" and settings.flight_provider.strip().lower() == "duffel" and settings.duffel_access_token)
    notice = None
    if use_duffel:
        try:
            provider = DuffelStaysProvider(settings)
            results = provider.search(city, check_in, check_out, adults, children, rooms, child_ages)
            return {"provider": provider.name, "data_status": provider.data_status, "notice": None if results else "Duffel Stays returned no properties for this city and dates.", "results": results}
        except StaysProviderError as exc:
            notice = f"{exc} Showing demo stays instead; they are illustrative only and cannot be booked."
    demo = DemoStaysProvider()
    return {
        "provider": demo.name,
        "data_status": demo.data_status,
        "notice": notice or DEMO_NOTICE.format(product="accommodation"),
        "results": demo.search(city, check_in, check_out, adults, children, rooms),
    }
