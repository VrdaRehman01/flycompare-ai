"""Search analytics computed from stored records only.

Rules:
- Searches are searches, not bookings or purchases.
- Fare averages are grouped by currency and data status; different currencies
  are never combined.
- Nothing is extrapolated: empty periods return empty series.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.airport_service import get_airport
from app.models import FareObservation, FlightSearchHistory

Range = Literal["7d", "30d", "90d", "all"]
RANGE_DAYS: dict[str, int | None] = {"7d": 7, "30d": 30, "90d": 90, "all": None}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _label(code: str | None, raw: str) -> str:
    airport = get_airport(code) if code else None
    if airport:
        return f"{airport.city} ({code})"
    return raw.strip()


def _key(code: str | None, raw: str) -> str:
    return code or raw.strip()


def _activity(rows: list[FlightSearchHistory], days: int | None, now: datetime) -> dict:
    today = now.date()
    counts = Counter(_aware(r.created_at).date() for r in rows)
    if days is not None and days <= 30:
        start = today - timedelta(days=days - 1)
        points = [{"start": (start + timedelta(days=i)).isoformat(), "count": counts.get(start + timedelta(days=i), 0)} for i in range(days)]
        return {"granularity": "day", "points": points}
    if days is not None:
        # Weekly buckets ending today.
        weeks = (days + 6) // 7
        start = today - timedelta(days=weeks * 7 - 1)
        points = []
        for i in range(weeks):
            b0 = start + timedelta(days=i * 7)
            points.append({"start": b0.isoformat(), "count": sum(c for d, c in counts.items() if b0 <= d < b0 + timedelta(days=7))})
        return {"granularity": "week", "points": points}
    if not rows:
        return {"granularity": "month", "points": []}
    first = min(counts)
    month = date(first.year, first.month, 1)
    points = []
    while month <= today:
        nxt = date(month.year + (month.month // 12), month.month % 12 + 1, 1)
        points.append({"start": month.isoformat(), "count": sum(c for d, c in counts.items() if month <= d < nxt)})
        month = nxt
    return {"granularity": "month", "points": points[-24:]}


def compute_analytics(db: Session, range_key: Range, user_id: int | None) -> dict:
    """Analytics for one user's searches (user_id) or for all searches (None)."""
    now = datetime.now(timezone.utc)
    days = RANGE_DAYS[range_key]

    base = select(FlightSearchHistory)
    if user_id is not None:
        base = base.where(FlightSearchHistory.user_id == user_id)
    all_rows = db.scalars(base.order_by(FlightSearchHistory.created_at.desc())).all()
    cutoff = now - timedelta(days=days) if days else None
    rows = [r for r in all_rows if cutoff is None or _aware(r.created_at) >= cutoff]

    dest_counts: Counter[str] = Counter()
    dest_labels: dict[str, str] = {}
    route_counts: Counter[tuple[str, str]] = Counter()
    route_labels: dict[tuple[str, str], tuple[str, str]] = {}
    for r in rows:
        dk = _key(r.destination_code, r.destination)
        dest_counts[dk] += 1
        dest_labels[dk] = _label(r.destination_code, r.destination)
        rk = (_key(r.origin_code, r.origin), dk)
        route_counts[rk] += 1
        route_labels[rk] = (_label(r.origin_code, r.origin), dest_labels[dk])

    total = len(rows)

    def share(n: int) -> float:
        return round(n / total, 4) if total else 0.0

    top_routes = [
        {"origin": o, "destination": d, "origin_label": route_labels[(o, d)][0], "destination_label": route_labels[(o, d)][1], "count": n, "share": share(n)}
        for (o, d), n in route_counts.most_common(8)
    ]

    heatmap: Counter[tuple[int, int]] = Counter()
    for r in rows:
        heatmap[(r.departure_date.month, r.departure_date.weekday())] += 1

    # Offer-level observations linked to the searches in scope and period.
    search_ids = [r.id for r in rows]
    observations: list[FareObservation] = []
    if search_ids:
        for i in range(0, len(search_ids), 500):
            observations.extend(db.scalars(select(FareObservation).where(FareObservation.search_id.in_(search_ids[i : i + 500]))).all())

    airline_offers: Counter[str] = Counter()
    airline_searches: dict[str, set[int]] = defaultdict(set)
    airline_codes: dict[str, str] = {}
    airline_logo_urls: dict[str, str] = {}
    fare_groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    fare_group_searches: dict[tuple[str, str], set[int]] = defaultdict(set)
    for o in observations:
        airline_offers[o.airline] += 1
        # Use the same provider-supplied logo identity as the Flights page.
        if o.airline_code and o.airline not in airline_codes:
            airline_codes[o.airline] = o.airline_code
        if o.airline_logo_url and o.airline not in airline_logo_urls:
            airline_logo_urls[o.airline] = o.airline_logo_url
        if o.search_id is not None:
            airline_searches[o.airline].add(o.search_id)
            fare_group_searches[(o.currency, o.data_status)].add(o.search_id)
        fare_groups[(o.currency, o.data_status)].append(o.price)

    lowest_by_group: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if r.min_price is not None and r.currency and r.data_status in {"test", "live"}:
            lowest_by_group[(r.currency, r.data_status)].append(r.min_price)

    fares = [
        {
            "currency": cur,
            "data_status": status,
            "offers": len(prices),
            "searches": len(fare_group_searches[(cur, status)]),
            "average_offer_price": round(sum(prices) / len(prices), 2),
            "median_offer_price": round(median(prices), 2),
            "average_lowest_price": (
                round(sum(lowest_by_group[(cur, status)]) / len(lowest_by_group[(cur, status)]), 2) if lowest_by_group[(cur, status)] else None
            ),
        }
        for (cur, status), prices in sorted(fare_groups.items(), key=lambda kv: -len(kv[1]))
    ]

    result_counts = [r.result_count for r in rows]
    most = top_routes[0] if top_routes else None
    statuses = Counter(r.data_status or "unknown" for r in rows)

    return {
        "range": range_key,
        "scope": "me" if user_id is not None else "all",
        "generated_at": now,
        "totals": {
            "all_time_searches": len(all_rows),
            "period_searches": total,
            "unique_destinations": len(dest_counts),
            "unique_routes": len(route_counts),
            "average_offers_per_search": round(sum(result_counts) / total, 1) if total else None,
            "searches_with_no_offers": sum(1 for c in result_counts if c == 0),
        },
        "most_searched_route": most,
        "activity": _activity(rows, days, now),
        "top_destinations": [{"code": k, "label": dest_labels[k], "count": n, "share": share(n)} for k, n in dest_counts.most_common(8)],
        "top_routes": top_routes,
        "cabins": [{"cabin": c, "count": n, "share": share(n)} for c, n in Counter(r.cabin for r in rows).most_common()],
        "passengers": [{"passengers": p, "count": n, "share": share(n)} for p, n in sorted(Counter(r.passengers for r in rows).items())],
        "trip_types": [{"trip_type": t, "count": n} for t, n in Counter(r.trip_type for r in rows).most_common()],
        "departure_months": [
            {"month": m, "count": n} for m, n in sorted(Counter(r.departure_date.strftime("%Y-%m") for r in rows).items())
        ],
        "passenger_types": {
            "adults": sum(r.passengers for r in rows),
            "children": sum(r.children or 0 for r in rows),
            "infants": sum(r.infants or 0 for r in rows),
        },
        "travel_heatmap": [{"month": m, "weekday": w, "count": n} for (m, w), n in sorted(heatmap.items())],
        "airlines": {
            "basis": "Airlines appearing in offers returned by searches (not bookings).",
            "items": [{"airline": a, "offers": n, "searches": len(airline_searches[a]), "airline_code": airline_codes.get(a), "airline_logo_url": airline_logo_urls.get(a)} for a, n in airline_offers.most_common()],
        },
        "fares": fares,
        "data_status_mix": dict(statuses),
    }
