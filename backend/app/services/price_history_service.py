"""Price history built from stored offer observations.

A trend is only reported as available when there are enough independent
observations (separate searches on separate days). One search is a snapshot,
never a trend.
"""

from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FareObservation, FlightSearchHistory

MIN_TREND_POINTS = 3
MIN_TREND_DAYS = 2


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def route_history(
    db: Session,
    origin: str,
    destination: str,
    departure_date: date,
    return_date: date | None,
    cabin: str,
    trip_type: str,
    passengers: int,
) -> dict:
    stmt = select(FareObservation).where(
        FareObservation.origin_code == origin,
        FareObservation.destination_code == destination,
        FareObservation.departure_date == departure_date,
        FareObservation.cabin == cabin,
        FareObservation.trip_type == trip_type,
        FareObservation.passengers == passengers,
    )
    stmt = stmt.where(FareObservation.return_date == return_date) if return_date else stmt.where(FareObservation.return_date.is_(None))
    observations = db.scalars(stmt.order_by(FareObservation.observed_at)).all()

    # One point per search (observation batch), kept separate per currency and data status.
    batches: dict[tuple[int | None, str, str], list[FareObservation]] = defaultdict(list)
    for o in observations:
        batches[(o.search_id, o.currency, o.data_status)].append(o)

    series: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (search_id, currency, status), items in batches.items():
        prices = [i.price for i in items]
        series[(currency, status)].append(
            {
                "observed_at": _aware(min(i.observed_at for i in items)),
                "lowest_price": round(min(prices), 2),
                "median_price": round(median(prices), 2),
                "offers": len(items),
            }
        )

    groups = []
    for (currency, status), points in series.items():
        points.sort(key=lambda p: p["observed_at"])
        distinct_days = len({p["observed_at"].date() for p in points})
        sufficient = len(points) >= MIN_TREND_POINTS and distinct_days >= MIN_TREND_DAYS
        change = None
        if sufficient:
            first, last = points[0]["lowest_price"], points[-1]["lowest_price"]
            change = {"absolute": round(last - first, 2), "percent": round((last - first) / first * 100, 1) if first else None}
        groups.append(
            {
                "currency": currency,
                "data_status": status,
                "points": points,
                "distinct_days": distinct_days,
                "sufficient_for_trend": sufficient,
                "lowest_change": change,
            }
        )
    groups.sort(key=lambda g: -len(g["points"]))
    return {
        "route": {"origin": origin, "destination": destination, "departure_date": departure_date, "return_date": return_date, "cabin": cabin, "trip_type": trip_type, "passengers": passengers},
        "requirements": {"min_points": MIN_TREND_POINTS, "min_distinct_days": MIN_TREND_DAYS},
        "groups": groups,
    }


def latest_route_snapshots(db: Session, routes: list[tuple[str, str]]) -> list[dict]:
    """Most recent observed lowest fare per route, for any travel date."""
    snapshots = []
    for origin, destination in routes:
        latest = db.scalar(
            select(FareObservation)
            .where(FareObservation.origin_code == origin, FareObservation.destination_code == destination)
            .order_by(FareObservation.observed_at.desc())
            .limit(1)
        )
        if latest is None:
            snapshots.append({"origin": origin, "destination": destination, "available": False})
            continue
        batch = db.scalars(
            select(FareObservation).where(
                FareObservation.search_id == latest.search_id,
                FareObservation.origin_code == origin,
                FareObservation.destination_code == destination,
                FareObservation.currency == latest.currency,
            )
        ).all() if latest.search_id is not None else [latest]
        cheapest = min(batch, key=lambda o: o.price)
        snapshots.append(
            {
                "origin": origin,
                "destination": destination,
                "available": True,
                "lowest_price": round(cheapest.price, 2),
                "currency": cheapest.currency,
                "data_status": cheapest.data_status,
                "airline": cheapest.airline,
                "observed_at": _aware(cheapest.observed_at),
                "departure_date": cheapest.departure_date,
                "return_date": cheapest.return_date,
                "trip_type": cheapest.trip_type,
                "cabin": cheapest.cabin,
                "passengers": cheapest.passengers,
            }
        )
    return snapshots


def route_daily_lowest(db: Session, origin: str, destination: str) -> dict:
    """Lowest observed offer per calendar day for a route across all travel dates.

    Kept separate per currency and data status. A trend needs observations on at
    least MIN_TREND_POINTS different days.
    """
    observations = db.scalars(
        select(FareObservation)
        .where(FareObservation.origin_code == origin, FareObservation.destination_code == destination)
        .order_by(FareObservation.observed_at)
    ).all()
    days: dict[tuple[str, str], dict[date, dict]] = defaultdict(dict)
    for o in observations:
        day = _aware(o.observed_at).date()
        bucket = days[(o.currency, o.data_status)].setdefault(day, {"lowest_price": o.price, "offers": 0, "searches": set()})
        bucket["lowest_price"] = min(bucket["lowest_price"], o.price)
        bucket["offers"] += 1
        bucket["searches"].add(o.search_id)
    groups = []
    for (currency, status), by_day in days.items():
        points = [
            {"date": d, "lowest_price": round(v["lowest_price"], 2), "offers": v["offers"], "searches": len(v["searches"])}
            for d, v in sorted(by_day.items())
        ]
        groups.append({"currency": currency, "data_status": status, "points": points, "sufficient_for_trend": len(points) >= MIN_TREND_POINTS})
    groups.sort(key=lambda g: -len(g["points"]))
    return {
        "route": {"origin": origin, "destination": destination},
        "basis": "Lowest offer observed each day across all travel dates searched for this route.",
        "requirements": {"min_days": MIN_TREND_POINTS},
        "groups": groups,
    }


CALENDAR_STALE_DAYS = 7  # observations older than this are flagged as old
CALENDAR_MIN_DAYS_FOR_TIERS = 3  # need at least this many dates before calling one "lower" or "higher"
CALENDAR_MIN_DAYS_PER_MONTH = 3  # a month needs this many observed dates to compete for "cheapest month"


def fare_calendar(
    db: Session,
    origin: str,
    destination: str,
    start: date,
    end: date,
    trip_type: str,
    cabin: str,
    passengers: int,
    children: int = 0,
    infants: int = 0,
    today: date | None = None,
) -> dict:
    """Lowest observed fare per departure date, for comparable searches only.

    Comparable means the same route, trip type, cabin and passengers (adults,
    children and infants, the last two taken from the originating search);
    currencies and data sources (live/test/demo) are never mixed. Each date shows
    when its fare was seen, because an observation is not current availability.
    Tiers (lower / middle / higher) are tertiles of the dates shown, and only
    when enough dates have data.
    """
    today = today or date.today()
    start = max(start, today)
    rows = db.scalars(
        select(FareObservation)
        .join(FlightSearchHistory, FlightSearchHistory.id == FareObservation.search_id)
        .where(
            FlightSearchHistory.children == children,
            FlightSearchHistory.infants == infants,
            FareObservation.origin_code == origin,
            FareObservation.destination_code == destination,
            FareObservation.trip_type == trip_type,
            FareObservation.cabin == cabin,
            FareObservation.passengers == passengers,
            FareObservation.departure_date >= start,
            FareObservation.departure_date <= end,
        )
    ).all()
    by_group: dict[tuple[str, str], dict[date, FareObservation]] = defaultdict(dict)
    for o in rows:
        best = by_group[(o.currency, o.data_status)].get(o.departure_date)
        # Cheapest per date; on a tie keep the most recent sighting.
        if best is None or o.price < best.price or (o.price == best.price and _aware(o.observed_at) > _aware(best.observed_at)):
            by_group[(o.currency, o.data_status)][o.departure_date] = o
    now = datetime.now(timezone.utc)
    groups = []
    for (currency, status), days in by_group.items():
        prices = sorted(o.price for o in days.values())
        tiers = len(prices) >= CALENDAR_MIN_DAYS_FOR_TIERS

        def tier_of(price: float) -> str:
            # Thirds by rank: the share of observed dates that are cheaper than this one.
            share = bisect_left(prices, price) / len(prices)
            return "low" if share < 1 / 3 else "mid" if share < 2 / 3 else "high"

        months: dict[str, list[float]] = defaultdict(list)
        out_days = {}
        for d, o in sorted(days.items()):
            age = (now - _aware(o.observed_at)).days
            tier = tier_of(o.price) if tiers else None
            out_days[d.isoformat()] = {
                "lowest_price": round(o.price, 2),
                "observed_at": _aware(o.observed_at).isoformat(),
                "stale": age > CALENDAR_STALE_DAYS,
                "airline": o.airline,
                "stops": o.stops,
                "return_date": o.return_date.isoformat() if o.return_date else None,
                "tier": tier,
            }
            months[d.strftime("%Y-%m")].append(o.price)
        month_summary = [
            {"month": m, "lowest_price": round(min(p), 2), "dates_observed": len(p)} for m, p in sorted(months.items())
        ]
        eligible = [m for m in month_summary if m["dates_observed"] >= CALENDAR_MIN_DAYS_PER_MONTH]
        cheapest_month = min(eligible, key=lambda m: m["lowest_price"])["month"] if len(eligible) >= 2 else None
        groups.append({
            "currency": currency, "data_status": status, "days": out_days, "months": month_summary,
            "cheapest_month": cheapest_month, "tiers_available": tiers,
        })
    groups.sort(key=lambda g: -len(g["days"]))
    return {
        "route": {"origin": origin, "destination": destination},
        "conditions": {"trip_type": trip_type, "cabin": cabin, "passengers": passengers, "children": children, "infants": infants},
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "basis": "Lowest fare seen in earlier FlyCompare searches for each departure date, with the same trip type, cabin and "
                 "number of passengers. These are past observations, not live prices or availability.",
        "rules": {
            "stale_after_days": CALENDAR_STALE_DAYS,
            "min_dates_for_comparison": CALENDAR_MIN_DAYS_FOR_TIERS,
            "min_dates_per_month": CALENDAR_MIN_DAYS_PER_MONTH,
        },
        "groups": groups,
    }
