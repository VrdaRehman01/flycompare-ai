from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import FareObservation, FlightSearchHistory
from app.services.analytics_service import compute_analytics
from app.services.price_history_service import route_history
from tests.conftest import register

NOW = datetime.now(timezone.utc)


def add_search(db, *, days_ago=0, origin="KHI", dest="DXB", user_id=None, cabin="Economy", passengers=1, prices=None, currency="USD", status="test", dep=date(2026, 12, 10), ret=date(2026, 12, 17)):
    created = NOW - timedelta(days=days_ago)
    prices = prices or []
    row = FlightSearchHistory(
        origin=f"X ({origin})", destination=f"Y ({dest})", origin_code=origin, destination_code=dest,
        departure_date=dep, return_date=ret, trip_type="round-trip" if ret else "one-way", passengers=passengers, cabin=cabin,
        result_count=len(prices), user_id=user_id, created_at=created, data_status=status,
        currency=currency if prices else None, min_price=min(prices) if prices else None,
    )
    db.add(row)
    db.flush()
    for i, p in enumerate(prices):
        db.add(FareObservation(
            search_id=row.id, observed_at=created, provider="Duffel", data_status=status, origin_code=origin, destination_code=dest,
            departure_date=dep, return_date=ret, trip_type=row.trip_type, cabin=cabin, passengers=passengers,
            offer_id=f"o{row.id}-{i}", airline="Gulf Air" if i % 2 else "Qatar Airways", price=p, currency=currency, stops=1, duration_minutes=300,
        ))
    db.commit()
    return row


def test_analytics_counts_periods_and_routes(db_session):
    add_search(db_session, days_ago=1, prices=[100, 200])
    add_search(db_session, days_ago=3, dest="LHR", cabin="Business", passengers=2, prices=[500])
    add_search(db_session, days_ago=40, dest="LHR")
    add_search(db_session, days_ago=200, dest="IST")

    week = compute_analytics(db_session, "7d", None)
    assert week["totals"]["period_searches"] == 2
    assert week["totals"]["all_time_searches"] == 4
    assert week["totals"]["unique_destinations"] == 2
    assert len(week["activity"]["points"]) == 7
    assert sum(p["count"] for p in week["activity"]["points"]) == 2
    assert {c["cabin"] for c in week["cabins"]} == {"Economy", "Business"}
    assert {p["passengers"] for p in week["passengers"]} == {1, 2}
    assert week["totals"]["average_offers_per_search"] == 1.5

    quarter = compute_analytics(db_session, "90d", None)
    assert quarter["totals"]["period_searches"] == 3
    assert quarter["most_searched_route"]["destination"] == "LHR"
    assert quarter["activity"]["granularity"] == "week"

    everything = compute_analytics(db_session, "all", None)
    assert everything["totals"]["period_searches"] == 4
    assert everything["activity"]["granularity"] == "month"
    assert sum(p["count"] for p in everything["activity"]["points"]) == 4


def test_analytics_never_mixes_currencies_or_data_statuses(db_session):
    add_search(db_session, prices=[100, 300], currency="USD")
    add_search(db_session, prices=[90], currency="EUR")
    add_search(db_session, prices=[1000], currency="USD", status="live")

    fares = compute_analytics(db_session, "30d", None)["fares"]
    groups = {(f["currency"], f["data_status"]): f for f in fares}
    assert set(groups) == {("USD", "test"), ("EUR", "test"), ("USD", "live")}
    assert groups[("USD", "test")]["average_offer_price"] == 200
    assert groups[("USD", "test")]["average_lowest_price"] == 100
    assert groups[("EUR", "test")]["average_offer_price"] == 90


def test_analytics_airlines_and_heatmap(db_session):
    add_search(db_session, prices=[100, 200, 300], dep=date(2026, 12, 10))  # Thursday
    data = compute_analytics(db_session, "30d", None)
    airlines = {a["airline"]: a for a in data["airlines"]["items"]}
    assert airlines["Qatar Airways"]["offers"] == 2 and airlines["Gulf Air"]["offers"] == 1
    assert data["travel_heatmap"] == [{"month": 12, "weekday": 3, "count": 1}]


def test_analytics_empty_state(db_session):
    data = compute_analytics(db_session, "all", None)
    assert data["totals"]["period_searches"] == 0
    assert data["most_searched_route"] is None
    assert data["activity"]["points"] == []
    assert data["fares"] == []


def test_personal_analytics_only_include_own_searches(client, db_session):
    me = register(client)
    add_search(db_session, user_id=me["id"], dest="DXB")
    add_search(db_session, user_id=None, dest="LHR")
    mine = client.get("/api/insights/analytics?range=30d&scope=me").json()
    assert mine["totals"]["period_searches"] == 1
    assert [d["code"] for d in mine["top_destinations"]] == ["DXB"]
    assert len(mine["recent_searches"]) == 1
    everyone = client.get("/api/insights/analytics?range=30d&scope=all").json()
    assert everyone["totals"]["period_searches"] == 2
    assert "recent_searches" not in everyone


def test_price_trend_requires_multiple_observations_on_multiple_days(db_session):
    add_search(db_session, days_ago=0, prices=[120, 150])
    one = route_history(db_session, "KHI", "DXB", date(2026, 12, 10), date(2026, 12, 17), "Economy", "round-trip", 1)
    assert one["groups"][0]["sufficient_for_trend"] is False
    assert len(one["groups"][0]["points"]) == 1

    add_search(db_session, days_ago=0, prices=[118])
    add_search(db_session, days_ago=0, prices=[119])
    same_day = route_history(db_session, "KHI", "DXB", date(2026, 12, 10), date(2026, 12, 17), "Economy", "round-trip", 1)
    assert len(same_day["groups"][0]["points"]) == 3
    assert same_day["groups"][0]["sufficient_for_trend"] is False  # all on one day

    add_search(db_session, days_ago=2, prices=[140])
    trend = route_history(db_session, "KHI", "DXB", date(2026, 12, 10), date(2026, 12, 17), "Economy", "round-trip", 1)
    group = trend["groups"][0]
    assert group["sufficient_for_trend"] is True
    assert group["points"][0]["lowest_price"] == 140  # oldest first
    assert group["lowest_change"]["absolute"] == pytest.approx(119 - 140)


def test_price_history_is_scoped_to_exact_search(db_session):
    add_search(db_session, prices=[100])
    add_search(db_session, prices=[100], cabin="Business")
    add_search(db_session, prices=[100], ret=date(2026, 12, 20))
    history = route_history(db_session, "KHI", "DXB", date(2026, 12, 10), date(2026, 12, 17), "Economy", "round-trip", 1)
    assert sum(len(g["points"]) for g in history["groups"]) == 1


def test_route_snapshot_endpoint(client, db_session):
    add_search(db_session, prices=[150, 99])
    data = client.get("/api/prices/routes?routes=KHI-DXB,KHI-LHR").json()
    assert data[0]["available"] is True and data[0]["lowest_price"] == 99 and data[0]["data_status"] == "test"
    assert data[1] == {"origin": "KHI", "destination": "LHR", "available": False}
    assert client.get("/api/prices/routes?routes=karachi").status_code == 422
