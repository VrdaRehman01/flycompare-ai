"""Group and private tours built around each city's curated sights.

Itineraries use real sights from ``travel_content``; operators, schedules,
ratings and prices are demo data until a tours provider is connected. Pricing
follows how tour operators charge: group tours per person (shared guide and
transport), private tours per party (dedicated guide and vehicle) plus
admissions per person, so private tours get cheaper per head as the party grows.
"""

from datetime import date

from app.data.travel_content import Sight
from app.services.destination_service import City
from app.services.travel_common import DEMO_NOTICE, cost_index, guide_for, seeded

OPERATORS = ("Demo Tours Co.", "Sample Journeys", "Example Guided Walks", "Testline Excursions")
LANGUAGES = (["English"], ["English", "Arabic"], ["English", "French"], ["English", "Spanish"], ["English", "Urdu"])


def _itineraries(city: City, sights: tuple[Sight, ...]) -> list[dict]:
    """Group sights into sensible half-day, full-day and evening itineraries."""
    out: list[dict] = []
    by_cat: dict[str, list[Sight]] = {}
    for s in sights:
        by_cat.setdefault(s.category, []).append(s)
    day_sights = [s for s in sights if s.slot != "evening" and s.hours < 5]
    if len(day_sights) >= 3:
        out.append({"title": f"Highlights of {city.city}", "stops": day_sights[:3], "start": "09:00",
                    "summary": f"The essential sights of {city.city} in one guided day."})
    culture = [s for s in by_cat.get("Culture", []) if s.hours < 5]
    if len(culture) >= 2:
        out.append({"title": f"{city.city} history & heritage", "stops": culture[1:4] if len(culture) > 3 else culture[:3], "start": "09:30",
                    "summary": "Monuments, museums and the stories behind them with an expert guide."})
    food = by_cat.get("Food", []) + by_cat.get("Shopping", [])
    if food:
        out.append({"title": f"{city.city} food & markets", "stops": food[:3], "start": "17:30",
                    "summary": "Taste local specialities and browse the markets with a local host."})
    evening = [s for s in sights if s.slot == "evening" and s.hours < 5]
    if len(evening) >= 2:
        out.append({"title": f"{city.city} by night", "stops": evening[:3], "start": "18:00",
                    "summary": "Sunset views and the city lit up after dark."})
    nature = [s for s in by_cat.get("Nature", []) + by_cat.get("Beach", []) + by_cat.get("Family", []) if s.hours < 5]
    if len(nature) >= 2:
        out.append({"title": f"{city.city} outdoors & family day", "stops": nature[:3], "start": "10:00",
                    "summary": "Parks, beaches and family favourites at an easy pace."})
    for s in sights:
        if s.hours >= 4 and s.category in ("Adventure", "Culture", "Nature"):
            out.append({"title": s.name, "stops": [s], "start": "06:00" if "sunrise" in s.name.lower() else "08:30" if s.slot == "morning" else "14:30",
                        "summary": s.blurb})
    seen, unique = set(), []
    for it in out:
        key = tuple(s.name for s in it["stops"])
        if key not in seen:
            seen.add(key)
            unique.append(it)
    return unique


def search_tours(city: City, on: date, travellers: int, kind: str) -> dict:
    guide = guide_for(city)
    base = {"data_status": "demo", "provider": "FlyCompare Demo Tours", "notice": DEMO_NOTICE.format(product="tours"), "kind": kind}
    if not guide:
        return {**base, "results": [], "notice": f"No tours are catalogued for {city.city} yet. Tours are available for the cities in our travel guides."}
    scale = (cost_index(city) / 110) ** 0.5
    out = []
    for it in _itineraries(city, guide.sights):
        stops: list[Sight] = it["stops"]
        hours = round(sum(s.hours for s in stops) + 0.5 * (len(stops) - 1), 1)
        admissions = sum(s.usd for s in stops)
        rng = seeded("tour", city.key, it["title"], kind)
        runs_today = rng.random() < 0.85 or on.weekday() < 5  # some group departures skip weekends
        if kind == "group" and not runs_today:
            continue
        operator = rng.choice(OPERATORS)
        if kind == "group":
            per_person = (14 + 6.5 * hours) * scale * (0.9 + 0.25 * rng.random()) + admissions
            total = per_person * travellers
            price = {"price_basis": "per person", "price_per_person": round(per_person, 2), "total_price": round(total, 2)}
            details = {
                "group_size_max": rng.choice([12, 15, 16, 20]),
                "start_times": [it["start"]] + ([f"{int(it['start'][:2]) + 1:02d}:{it['start'][3:]}"] if hours <= 4 and rng.random() < 0.5 else []),
                "pickup": "Meeting point in the city centre" if rng.random() < 0.6 else "Hotel pickup from central hotels",
                "spots_left": rng.choice([None, None, 3, 5, 8]),
            }
        else:
            vehicle = "Sedan" if travellers <= 3 else "Minivan" if travellers <= 7 else "Minibus"
            vehicle_cost = {"Sedan": 0, "Minivan": 25, "Minibus": 60}[vehicle]
            party = (38 * hours + 30 + vehicle_cost) * scale * (0.9 + 0.25 * rng.random())
            total = party + admissions * travellers
            price = {"price_basis": "per party", "price_per_person": round(total / travellers, 2), "total_price": round(total, 2)}
            details = {"vehicle": vehicle, "start_times": ["Flexible"], "pickup": "Pickup from your hotel or address", "customisable": True}
        out.append({
            "id": f"tour-{seeded(city.key, it['title'], kind).randrange(16**10):010x}",
            "kind": kind, "title": it["title"] if kind == "group" else f"Private: {it['title']}",
            "summary": it["summary"], "operator": operator,
            "stops": [{"name": s.name, "category": s.category, "hours": s.hours, "blurb": s.blurb} for s in stops],
            "categories": sorted({s.category for s in stops}),
            "duration_hours": hours,
            "languages": rng.choice(LANGUAGES),
            "rating": round(4.1 + 0.8 * rng.random(), 1), "reviews": int(15 + rng.random() ** 2 * 2200),
            "includes": ["Licensed guide", "Transport between stops" if len(stops) > 1 else "Guide for the whole visit"] + (["Admission tickets"] if admissions else []) + (["Bottled water"] if hours >= 4 else []),
            "excludes": ["Meals unless stated", "Gratuities"],
            "admission_included_usd": admissions,
            "free_cancellation": "Up to 24 hours before the start",
            "currency": "USD", **price, **details,
        })
    out.sort(key=lambda t: (-t["rating"], t["total_price"]))
    return {**base, "results": out}
