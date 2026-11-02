"""Fare calendar: only comparable observations, honest tiers and cheapest-month rules."""

from datetime import date, datetime, timedelta, timezone

from app.models import FareObservation, FlightSearchHistory
from app.services.price_history_service import fare_calendar

TODAY = date(2026, 11, 1)


def observe(db, day, price, *, trip="one-way", cabin="Economy", adults=1, children=0, currency="USD", status="test",
            seen_days_ago=0, route=("KHI", "DXB")):
    search = FlightSearchHistory(origin=route[0], destination=route[1], origin_code=route[0], destination_code=route[1], departure_date=day,
                                 trip_type=trip, passengers=adults, children=children, cabin=cabin, result_count=1, data_status=status)
    db.add(search)
    db.flush()
    db.add(FareObservation(search_id=search.id, provider="Duffel", data_status=status, origin_code=route[0], destination_code=route[1],
                           departure_date=day, trip_type=trip, cabin=cabin, passengers=adults, offer_id=f"o{search.id}", airline="X",
                           price=price, currency=currency, stops=0,
                           observed_at=datetime.now(timezone.utc) - timedelta(days=seen_days_ago)))
    db.commit()


def cal(db, **kw):
    args = dict(trip_type="one-way", cabin="Economy", passengers=1, today=TODAY)
    args.update(kw)
    return fare_calendar(db, "KHI", "DXB", TODAY, TODAY + timedelta(days=90), **args)


def test_keeps_lowest_per_date_and_ignores_incomparable_searches(db_session):
    d = TODAY + timedelta(days=10)
    observe(db_session, d, 120)
    observe(db_session, d, 99)
    observe(db_session, d, 50, trip="round-trip")        # different trip type
    observe(db_session, d, 40, cabin="Business")         # different cabin
    observe(db_session, d, 30, adults=2)                 # different passenger count
    observe(db_session, d, 20, children=1)               # child fares differ
    observe(db_session, d, 10, route=("KHI", "DOH"))     # different route
    groups = cal(db_session)["groups"]
    assert len(groups) == 1 and groups[0]["days"][d.isoformat()]["lowest_price"] == 99


def test_currencies_and_data_sources_are_never_mixed(db_session):
    d = TODAY + timedelta(days=5)
    observe(db_session, d, 100)
    observe(db_session, d, 300, currency="PKR")
    observe(db_session, d, 90, status="live")
    keys = {(g["currency"], g["data_status"]) for g in cal(db_session)["groups"]}
    assert keys == {("USD", "test"), ("PKR", "test"), ("USD", "live")}


def test_past_dates_are_excluded(db_session):
    observe(db_session, TODAY - timedelta(days=1), 80)
    assert cal(db_session)["groups"] == []


def test_tiers_need_enough_dates(db_session):
    observe(db_session, TODAY + timedelta(days=3), 100)
    observe(db_session, TODAY + timedelta(days=4), 200)
    g = cal(db_session)["groups"][0]
    assert g["tiers_available"] is False and all(v["tier"] is None for v in g["days"].values())
    observe(db_session, TODAY + timedelta(days=5), 300)
    g = cal(db_session)["groups"][0]
    assert [g["days"][(TODAY + timedelta(days=n)).isoformat()]["tier"] for n in (3, 4, 5)] == ["low", "mid", "high"]


def test_old_observations_are_flagged(db_session):
    observe(db_session, TODAY + timedelta(days=3), 100, seen_days_ago=20)
    assert cal(db_session)["groups"][0]["days"][(TODAY + timedelta(days=3)).isoformat()]["stale"] is True


def test_cheapest_month_needs_two_months_with_enough_data(db_session):
    for n in range(3):
        observe(db_session, date(2026, 11, 10 + n), 150 + n)
    assert cal(db_session)["groups"][0]["cheapest_month"] is None  # only one month
    for n in range(3):
        observe(db_session, date(2026, 12, 10 + n), 120 + n)
    g = cal(db_session)["groups"][0]
    assert g["cheapest_month"] == "2026-12"
    assert g["months"] == [{"month": "2026-11", "lowest_price": 150, "dates_observed": 3}, {"month": "2026-12", "lowest_price": 120, "dates_observed": 3}]


def test_endpoint_validates_window(client):
    assert client.get("/api/prices/calendar?origin=KHI&destination=DXB&start=2026-12-01&end=2026-11-01").status_code == 422
    ok = client.get("/api/prices/calendar?origin=KHI&destination=DXB&start=2026-12-01&end=2027-01-31").json()
    assert ok["groups"] == [] and "not live prices" in ok["basis"]
