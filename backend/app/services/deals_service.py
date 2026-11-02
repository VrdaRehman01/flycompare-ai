"""Flight deals and popular routes, built only from stored searches.

Deals
    Every deal is a fare a provider returned in an earlier FlyCompare search,
    for a departure date that has not passed. Fares are grouped only when they
    are comparable: same route, trip type, cabin, passenger count, currency and
    data source (live/test). Each deal says how old it is:

    * ``last_seen``   seen within FRESH_DAYS: a recent observation, not a quote.
    * ``historical``  older than FRESH_DAYS.

    A price change is reported only against an earlier search for the *same*
    departure and return dates under the same conditions; nothing is called a
    discount without that comparison.

Popular routes
    ``me``  the signed-in user's own searches, with exact timestamps.
    ``all`` an aggregate over every search. A route is listed only after
            MIN_PUBLIC_SEARCHES searches, and only the day of the latest search
            is shown, so no individual's activity can be read from it.
"""

from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FareObservation, FlightSearchHistory, SavedRoute
from app.services import airport_service, destination_service, price_history_service

FRESH_DAYS = 7
RECENT_HOURS = 48
MIN_FLEX_DATES = 3
MIN_BUDGET_GROUP = 3
MIN_PUBLIC_SEARCHES = 3
WEEKEND_OUT = {3, 4, 5}  # Thu, Fri, Sat
WEEKEND_BACK = {6, 0}  # Sun, Mon
WEEKEND_NIGHTS = (1, 4)

CATEGORIES = [
    {"key": "cheapest", "label": "Cheapest", "rule": "All deals, lowest fare first (within each currency and data source)."},
    {"key": "international", "label": "International", "rule": "Destination is in a different country from the departure airport."},
    {"key": "domestic", "label": "Domestic", "rule": "Departure and destination airports are in the same country."},
    {"key": "weekend", "label": "Weekend trips",
     "rule": "Round trips leaving Thursday to Saturday and returning Sunday or Monday, 1 to 4 nights."},
    {"key": "flexible", "label": "Flexible dates",
     "rule": f"Routes with fares seen for at least {MIN_FLEX_DATES} different departure dates; shows the lowest of them."},
    {"key": "budget", "label": "Budget",
     "rule": f"The lowest third of fares from the same departure airport, currency and data source (needs {MIN_BUDGET_GROUP}+ routes)."},
    {"key": "recent", "label": "Just seen", "rule": f"Seen in a search within the last {RECENT_HOURS} hours."},
]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _place(code: str) -> dict:
    a = airport_service.get_airport(code)
    if a is None:
        # Metro codes (NYC, LON, TYO…) name a city served by several airports.
        members = airport_service.metro_codes().get(code)
        a = airport_service.get_airport(members[0]) if members else None
    if a is None:
        return {"code": code, "city": code, "country": None, "country_code": None, "key": None}
    return {"code": code, "city": a.city, "country": a.country, "country_code": a.country_code, "key": f"{a.city}|{a.country_code}"}


def _offer_fields(o: FareObservation) -> dict:
    return {
        "price": round(o.price, 2),
        "airline": o.airline,
        "airline_code": o.airline_code,
        "airline_logo_url": o.airline_logo_url,
        "stops": o.stops,
        "departure_date": o.departure_date.isoformat(),
        "return_date": o.return_date.isoformat() if o.return_date else None,
        "observed_at": _aware(o.observed_at).isoformat(),
    }


def deals(db: Session, origin: str | None = None, today: date | None = None, now: datetime | None = None) -> dict:
    today = today or date.today()
    now = now or datetime.now(timezone.utc)
    query = select(FareObservation).where(FareObservation.departure_date >= today)
    if origin:
        query = query.where(FareObservation.origin_code == origin)
    rows = db.scalars(query).all()

    groups: dict[tuple, list[FareObservation]] = defaultdict(list)
    for o in rows:
        groups[(o.origin_code, o.destination_code, o.trip_type, o.cabin, o.passengers, o.currency, o.data_status)].append(o)

    items = []
    for (orig, dest, trip, cabin, pax, currency, status), obs in groups.items():
        latest_search = max(obs, key=lambda o: (_aware(o.observed_at), o.search_id or 0)).search_id
        latest = [o for o in obs if o.search_id == latest_search]
        head = min(latest, key=lambda o: o.price)
        age_hours = (now - _aware(head.observed_at)).total_seconds() / 3600

        # Same dates, same conditions, an earlier search: the only valid comparison.
        earlier = [o for o in obs if o.search_id != latest_search and o.departure_date == head.departure_date
                   and o.return_date == head.return_date and _aware(o.observed_at) < _aware(head.observed_at)]
        change = None
        if earlier:
            prev_search = max(earlier, key=lambda o: _aware(o.observed_at)).search_id
            prev = min((o for o in earlier if o.search_id == prev_search), key=lambda o: o.price)
            diff = round(head.price - prev.price, 2)
            change = {
                "previous_price": round(prev.price, 2), "previous_observed_at": _aware(prev.observed_at).isoformat(),
                "absolute": diff, "percent": round(diff / prev.price * 100, 1) if prev.price else None,
            }

        by_date: dict[date, FareObservation] = {}
        for o in obs:
            if o.departure_date not in by_date or o.price < by_date[o.departure_date].price:
                by_date[o.departure_date] = o
        cheapest_any = min(by_date.values(), key=lambda o: o.price)

        o_place, d_place = _place(orig), _place(dest)
        cats = []
        if o_place["country_code"] and d_place["country_code"]:
            cats.append("domestic" if o_place["country_code"] == d_place["country_code"] else "international")
        if trip == "round-trip" and head.return_date:
            nights = (head.return_date - head.departure_date).days
            if head.departure_date.weekday() in WEEKEND_OUT and head.return_date.weekday() in WEEKEND_BACK and WEEKEND_NIGHTS[0] <= nights <= WEEKEND_NIGHTS[1]:
                cats.append("weekend")
        if len(by_date) >= MIN_FLEX_DATES:
            cats.append("flexible")
        if age_hours <= RECENT_HOURS:
            cats.append("recent")

        items.append({
            "id": f"{orig}-{dest}-{trip}-{cabin}-{pax}-{currency}-{status}",
            "origin": o_place, "destination": d_place,
            "themes": list(destination_service.CURATED.get(d_place["key"] or "", ())),
            "trip_type": trip, "cabin": cabin, "passengers": pax, "currency": currency, "data_status": status,
            "provider": head.provider,
            "kind": "last_seen" if age_hours <= FRESH_DAYS * 24 else "historical",
            "age_hours": round(age_hours, 1),
            **_offer_fields(head),
            "change": change,
            "flexibility": {
                "dates_observed": len(by_date),
                "first_date": min(by_date).isoformat(), "last_date": max(by_date).isoformat(),
                "cheapest": {"departure_date": cheapest_any.departure_date.isoformat(),
                             "return_date": cheapest_any.return_date.isoformat() if cheapest_any.return_date else None,
                             "price": round(cheapest_any.price, 2), "observed_at": _aware(cheapest_any.observed_at).isoformat()},
            },
            "categories": cats,
        })

    # Budget: lowest third among routes from the same origin, currency and data source.
    pools: dict[tuple, list[dict]] = defaultdict(list)
    for item in items:
        pools[(item["origin"]["code"], item["currency"], item["data_status"])].append(item)
    for pool in pools.values():
        if len(pool) < MIN_BUDGET_GROUP:
            continue
        ranked = sorted(pool, key=lambda i: i["price"])
        for item in ranked[: max(1, len(ranked) // 3)]:
            item["categories"].append("budget")

    items.sort(key=lambda i: (i["currency"], i["data_status"] != "live", i["price"]))
    return {
        "generated_at": now.isoformat(),
        "origin": origin,
        "basis": "Fares returned by providers in earlier FlyCompare searches, for departure dates that have not passed. "
                 "They are observations, not live prices: search to see current availability.",
        "rules": {"fresh_days": FRESH_DAYS, "recent_hours": RECENT_HOURS, "min_public_searches": MIN_PUBLIC_SEARCHES},
        "categories": CATEGORIES,
        "items": items,
    }


def popular_routes(db: Session, scope: str, user_id: int | None = None, limit: int = 12) -> dict:
    query = select(FlightSearchHistory).where(
        FlightSearchHistory.origin_code.is_not(None), FlightSearchHistory.destination_code.is_not(None),
        FlightSearchHistory.trip_type != "multi-city",
    )
    if scope == "me":
        query = query.where(FlightSearchHistory.user_id == user_id)
    searches = db.scalars(query).all()

    by_route: dict[tuple[str, str], list[FlightSearchHistory]] = defaultdict(list)
    for s in searches:
        by_route[(s.origin_code, s.destination_code)].append(s)
    if scope == "all":
        by_route = {k: v for k, v in by_route.items() if len(v) >= MIN_PUBLIC_SEARCHES}
    total = sum(len(v) for v in by_route.values())
    saved = set()
    if scope == "me" and user_id is not None:
        saved = {(r.origin_code, r.destination_code) for r in db.scalars(select(SavedRoute).where(SavedRoute.user_id == user_id))}

    ranked = sorted(by_route.items(), key=lambda kv: (-len(kv[1]), -max(_aware(s.created_at) for s in kv[1]).timestamp()))[:limit]
    snapshots = {(s["origin"], s["destination"]): s for s in price_history_service.latest_route_snapshots(db, [k for k, _ in ranked])}
    routes = []
    for (orig, dest), rows in ranked:
        last = max(rows, key=lambda s: _aware(s.created_at))
        status_mix: dict[str, int] = defaultdict(int)
        for s in rows:
            status_mix[s.data_status or "unknown"] += 1
        entry = {
            "origin": _place(orig), "destination": _place(dest),
            "searches": len(rows), "share": round(len(rows) / total * 100, 1) if total else 0,
            "data_status_mix": dict(status_mix),
            "last_fare": snapshots.get((orig, dest)) if snapshots.get((orig, dest), {}).get("available") else None,
        }
        if scope == "me":
            entry.update({
                "last_searched_at": _aware(last.created_at).isoformat(),
                "saved": (orig, dest) in saved,
                "last_trip": {"trip_type": last.trip_type, "departure_date": last.departure_date.isoformat(),
                              "return_date": last.return_date.isoformat() if last.return_date else None,
                              "cabin": last.cabin, "passengers": last.passengers},
            })
        else:
            entry["last_searched_day"] = _aware(last.created_at).date().isoformat()  # day only, by design
        routes.append(entry)
    return {
        "scope": scope, "total_searches": total, "routes": routes,
        "basis": ("Your own searches on FlyCompare." if scope == "me" else
                  f"All FlyCompare searches, anonymous and aggregated. Routes appear after {MIN_PUBLIC_SEARCHES} searches; "
                  "only the day of the latest search is shown."),
        "min_public_searches": MIN_PUBLIC_SEARCHES,
    }


def saved_routes(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(select(SavedRoute).where(SavedRoute.user_id == user_id).order_by(SavedRoute.created_at.desc())).all()
    snapshots = {(s["origin"], s["destination"]): s for s in price_history_service.latest_route_snapshots(db, [(r.origin_code, r.destination_code) for r in rows])}
    return [
        {"origin": _place(r.origin_code), "destination": _place(r.destination_code), "saved_at": _aware(r.created_at).isoformat(),
         "last_fare": snapshots.get((r.origin_code, r.destination_code)) if snapshots.get((r.origin_code, r.destination_code), {}).get("available") else None}
        for r in rows
    ]
