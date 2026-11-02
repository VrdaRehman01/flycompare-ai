"""Trip planner: a day-by-day itinerary, weather outlook and budget estimate.

Scheduling: each day has a time budget set by the chosen pace (arrival and
departure days are shorter). Sights are ranked by interest match, then editorial
popularity, and placed into the slot they suit best (morning/afternoon/evening),
with lunch and dinner breaks. Sights of five hours or more fill a full day.
Weather uses the Open-Meteo forecast when the trip is within 16 days, otherwise
last year's observed climate for that month. Costs are estimates in USD from
the city's cost index; flights are excluded because they are searched live.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil

from app.core.config import get_settings
from app.data.travel_content import Sight
from app.providers.weather_provider import MAX_FORECAST_DAYS, OpenMeteoProvider, Point, WeatherUnavailable
from app.services import guide_service
from app.services.destination_service import City
from app.services.travel_common import city_summary, cost_index, guide_for

PACE_HOURS = {"relaxed": 5.5, "balanced": 8.0, "packed": 10.5}
PACE_START = {"relaxed": 10.0, "balanced": 9.0, "packed": 8.0}
BUDGET = {  # share of the city's mid-range hotel night, per room / per person per day
    "budget": {"stay": 0.5, "food": 0.22, "transport": 0.06},
    "mid": {"stay": 1.0, "food": 0.4, "transport": 0.1},
    "luxury": {"stay": 2.3, "food": 0.85, "transport": 0.25},
}


@dataclass
class _Day:
    date: date
    kind: str  # arrival | full | departure
    capacity: float


def _clock(h: float) -> str:
    h = round(h * 4) / 4
    return f"{int(h) % 24:02d}:{int(round((h - int(h)) * 60)):02d}"


MUST_SEES = 2  # sights outside the chosen interests that still make the plan

# Interest-themed ideas used for open slots, so different interests give different days.
FILLERS = {
    "Food": ("Food crawl in {area}", "Graze on street food and local specialities."),
    "Shopping": ("Shopping in {area}", "Browse local markets, boutiques and malls."),
    "Nature": ("Green space in {area}", "A park, garden or waterfront walk to slow down."),
    "Beach": ("Beach time", "Swim, sunbathe or walk the shore."),
    "Family": ("Family time in {area}", "A playground, aquarium or ice-cream stop for the kids."),
    "City": ("Walk {area}", "Wander the streets, people-watch and find a viewpoint."),
    "Culture": ("Gallery or museum in {area}", "Pick a smaller museum, gallery or historic street."),
    "Adventure": ("Outdoor activity", "Try a bike tour, kayak or local excursion."),
}


def _rank(sights: tuple[Sight, ...], interests: list[str]) -> list[Sight]:
    """Matching sights first; with interests chosen, only the top must-sees from other categories stay."""
    wanted = set(interests)
    matching = [s for s in sights if s.category in wanted]
    others = [s for s in sights if s.category not in wanted]
    if wanted:
        others = others[:MUST_SEES]
    return matching + others


def _fits(s: Sight, slot: str) -> bool:
    return s.slot == slot or s.slot == "any" or (slot == "afternoon" and s.slot == "morning")


def build_days(start: date, end: date, pace: str) -> list[_Day]:
    nights = (end - start).days
    days = []
    for i in range(nights + 1):
        d = start + timedelta(days=i)
        if i == 0:
            days.append(_Day(d, "arrival", min(4.0, PACE_HOURS[pace] / 2)))
        elif i == nights:
            days.append(_Day(d, "departure", 3.0))
        else:
            days.append(_Day(d, "full", PACE_HOURS[pace]))
    return days


def schedule(city: City, sights: tuple[Sight, ...], days: list[_Day], interests: list[str], pace: str, areas: list[str]) -> list[dict]:
    pool = _rank(sights, interests)
    used: set[str] = set()
    themes = [i for i in interests if i in FILLERS] or ["City"]
    filler_n = 0
    out = []
    for n, day in enumerate(days):
        area = areas[n % len(areas)] if areas else city.city
        items: list[dict] = []
        if day.kind == "arrival":
            slots, t = ["afternoon", "evening"], 15.0
            items.append({"time": "Arrival", "kind": "travel", "title": f"Arrive in {city.city} and check in", "detail": "Transfer from the airport and settle in."})
        elif day.kind == "departure":
            slots, t = ["morning"], PACE_START[pace]
        else:
            slots, t = ["morning", "afternoon", "evening"], PACE_START[pace]
            if pace == "packed":
                slots.insert(1, "afternoon")
        left = day.capacity
        lunch = dinner = False
        # A long excursion (5h+) takes over a full day when the pace allows it.
        if day.kind == "full":
            long = next((s for s in pool if s.name not in used and s.hours >= 5), None)
            if long and (long.category in interests or not interests or pace != "relaxed"):
                used.add(long.name)
                begin = 6.0 if "sunrise" in long.name.lower() else 8.5 if long.slot == "morning" else 14.0
                items.append({"time": _clock(begin), "kind": "sight", "title": long.name, "category": long.category, "hours": long.hours, "usd": long.usd, "detail": long.blurb})
                left -= long.hours
                finish = begin + long.hours
                t = finish + 0.5
                # After a long excursion only add what still fits comfortably in the day.
                slots = [] if finish >= 17 else ["evening"] if finish >= 13 else ["afternoon", "evening"]
        for slot in slots:
            if slot == "afternoon" and not lunch and 11.5 <= t <= 14.5:
                items.append({"time": _clock(max(t, 12.5)), "kind": "meal", "title": f"Lunch in {area}", "detail": "Pick somewhere local near your last stop."})
                t = max(t, 12.5) + 1.0
                lunch = True
            if slot == "evening":
                t = max(t, 17.5)
            pick = next((s for s in pool if s.name not in used and s.hours < 5 and s.hours <= left + 0.5 and _fits(s, slot)), None)
            if pick and slot == "evening" and t > 20.5:
                pick = None
            if pick and slot == "evening" and not dinner and t + pick.hours > 21.5:
                # Eat first when the evening activity runs late.
                items.append({"time": _clock(t), "kind": "meal", "title": "Early dinner", "detail": f"Eat in {area} before the evening activity."})
                dinner = True
                t += 1.25
            if pick:
                used.add(pick.name)
                items.append({"time": _clock(t), "kind": "sight", "title": pick.name, "category": pick.category, "hours": pick.hours, "usd": pick.usd, "detail": pick.blurb})
                t += pick.hours + 0.5
                left -= pick.hours
            elif slot != "evening" and day.kind != "departure":
                title, detail = FILLERS[themes[filler_n % len(themes)]]
                filler_n += 1
                items.append({"time": _clock(t), "kind": "free", "title": title.format(area=area), "detail": detail})
                t += 2.0
            if slot == "evening" and not dinner:
                items.append({"time": _clock(max(t, 19.5)), "kind": "meal", "title": "Dinner", "detail": f"Try a restaurant in {area}."})
                dinner = True
        if day.kind == "departure":
            items.append({"time": "Departure", "kind": "travel", "title": "Check out and head to the airport", "detail": f"Allow time to reach {city.primary.name} ({city.primary.code})."})
        elif not dinner:
            items.append({"time": _clock(max(t, 19.5)), "kind": "meal", "title": "Dinner", "detail": f"Try a restaurant in {area}."})
        title = {"arrival": "Arrival", "departure": "Departure"}.get(day.kind) or next((i["title"] for i in items if i["kind"] == "sight"), f"Explore {area}")
        out.append({"date": day.date.isoformat(), "kind": day.kind, "title": title, "area": area, "items": items,
                    "activities_usd": sum(i.get("usd", 0) for i in items)})
    return out


def _weather(city: City, start: date, end: date) -> dict | None:
    settings = get_settings()
    if not settings.travel_external_data_enabled:
        return None
    today = date.today()
    if (start - today).days <= MAX_FORECAST_DAYS - 1:
        try:
            days = min((end - start).days + 1, MAX_FORECAST_DAYS - (start - today).days)
            data = OpenMeteoProvider().forecast([Point(city.key, city.lat, city.lon)], start, days)[city.key]
            return {"kind": "forecast", "source": "Open-Meteo forecast (CC BY 4.0)", "days": data["daily"]}
        except (WeatherUnavailable, KeyError):
            pass
    clim = guide_service.climate(city)
    if not clim:
        return None
    months = {start.month, end.month}
    return {"kind": "climate", "source": clim["source"], "months": [m for m in clim["months"] if m["month"] in months]}


def _tips(weather: dict | None, guide_tips: list[str]) -> list[str]:
    tips = []
    highs: list[float] = []
    wet = 0
    if weather and weather["kind"] == "forecast":
        highs = [d["max_c"] for d in weather["days"] if d.get("max_c") is not None]
        wet = sum(1 for d in weather["days"] if (d.get("precipitation_probability") or 0) >= 50)
    elif weather:
        highs = [m["avg_high_c"] for m in weather["months"]]
        wet = max((m["rainy_days"] for m in weather["months"]), default=0) // 4
    if highs and max(highs) >= 32:
        tips.append("Expect heat: plan outdoor sights early or late, carry water and sun protection.")
    if highs and min(highs) <= 10:
        tips.append("Pack warm layers and a jacket for cold days.")
    if wet >= 2:
        tips.append("Rain is likely on some days: pack an umbrella and keep indoor sights as backups.")
    return tips + guide_tips


def plan_trip(city: City, start: date, end: date, travellers: int, interests: list[str], pace: str, budget: str) -> dict:
    guide = guide_for(city)
    days = build_days(start, end, pace)
    areas = [a.name for a in guide.areas] if guide else []
    itinerary = schedule(city, guide.sights if guide else (), days, interests, pace, areas)
    nights = (end - start).days
    rooms = ceil(travellers / 2)
    idx = cost_index(city)
    b = BUDGET[budget]
    activities = sum(d["activities_usd"] for d in itinerary) * travellers
    stay = idx * b["stay"] * nights * rooms
    food = idx * b["food"] * travellers * (nights + 1)
    transport = idx * b["transport"] * travellers * (nights + 1) + idx * 0.3 * 2  # plus airport transfers both ways
    weather = _weather(city, start, end)
    return {
        "city": city_summary(city),
        "curated": bool(guide),
        "start": start.isoformat(), "end": end.isoformat(), "nights": nights, "travellers": travellers,
        "pace": pace, "budget": budget, "interests": interests,
        "days": itinerary,
        "costs": {
            "currency": "USD",
            "lines": [
                {"label": f"Accommodation ({rooms} room{'s' if rooms > 1 else ''} × {nights} night{'s' if nights != 1 else ''})", "amount": round(stay)},
                {"label": "Food and drink", "amount": round(food)},
                {"label": "Local transport and airport transfers", "amount": round(transport)},
                {"label": "Sights and activities (typical admission)", "amount": round(activities)},
            ],
            "total": round(stay + food + transport + activities),
            "excludes": "Flights are not included; search them for live fares.",
            "basis": f"Estimated from typical {budget}-level prices in {city.city}. Not a quote.",
        },
        "weather": weather,
        "tips": _tips(weather, list(guide.tips) if guide else []),
        "note": None if guide else f"There is no curated guide for {city.city} yet, so the plan has free days you can fill yourself.",
    }
