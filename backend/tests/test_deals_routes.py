"""Deals and popular routes: only comparable observations, honest labels, private personal data."""

from datetime import date, datetime, timedelta, timezone

from app.models import FareObservation, FlightSearchHistory
from app.services import deals_service
from tests.conftest import make_client, register

TODAY = date(2026, 11, 2)  # a Monday
NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


def search(db, origin="KHI", dest="DXB", *, prices=(100.0,), dep=TODAY + timedelta(days=10), ret=None, trip="one-way", cabin="Economy",
           adults=1, currency="USD", status="test", hours_ago=1.0, user_id=None):
    when = NOW - timedelta(hours=hours_ago)
    s = FlightSearchHistory(origin=origin, destination=dest, origin_code=origin, destination_code=dest, departure_date=dep, return_date=ret,
                            trip_type=trip, passengers=adults, cabin=cabin, result_count=len(prices), data_status=status, user_id=user_id, created_at=when)
    db.add(s)
    db.flush()
    for i, p in enumerate(prices):
        db.add(FareObservation(search_id=s.id, provider="Duffel", data_status=status, origin_code=origin, destination_code=dest, departure_date=dep,
                               return_date=ret, trip_type=trip, cabin=cabin, passengers=adults, offer_id=f"o{s.id}-{i}", airline="Example Air",
                               airline_code="EA", price=p, currency=currency, stops=0, observed_at=when))
    db.commit()
    return s


def get(db, **kw):
    return deals_service.deals(db, today=TODAY, now=NOW, **kw)["items"]


def test_latest_search_is_the_headline_and_conditions_are_never_mixed(db_session):
    search(db_session, prices=(120, 140), hours_ago=30)
    search(db_session, prices=(150, 130), hours_ago=2)                    # latest search: headline 130
    search(db_session, prices=(60,), cabin="Business")                   # different cabin
    search(db_session, prices=(70,), adults=2)                           # different passengers
    search(db_session, prices=(80,), currency="PKR")                     # different currency
    search(db_session, prices=(90,), status="live")                      # different data source
    items = get(db_session)
    usd_test_economy = [i for i in items if (i["cabin"], i["passengers"], i["currency"], i["data_status"]) == ("Economy", 1, "USD", "test")]
    assert len(items) == 5 and len(usd_test_economy) == 1
    assert usd_test_economy[0]["price"] == 130 and usd_test_economy[0]["airline_code"] == "EA"


def test_departed_dates_are_excluded(db_session):
    search(db_session, dep=TODAY - timedelta(days=1))
    assert get(db_session) == []


def test_change_only_against_the_same_dates(db_session):
    search(db_session, prices=(150,), dep=TODAY + timedelta(days=20), hours_ago=50)  # different date: not comparable
    search(db_session, prices=(100,), hours_ago=1)
    assert get(db_session)[0]["change"] is None
    search(db_session, prices=(130,), hours_ago=26)  # same dates, earlier
    change = get(db_session)[0]["change"]
    assert change["previous_price"] == 130 and change["absolute"] == -30 and change["percent"] == -23.1


def test_freshness_labels(db_session):
    search(db_session, hours_ago=10 * 24)
    item = get(db_session)[0]
    assert item["kind"] == "historical" and "recent" not in item["categories"]
    search(db_session, "KHI", "DOH", hours_ago=3)
    doha = next(i for i in get(db_session) if i["destination"]["code"] == "DOH")
    assert doha["kind"] == "last_seen" and "recent" in doha["categories"]


def test_weekend_domestic_and_flexible_rules(db_session):
    friday = date(2026, 11, 13)
    search(db_session, "KHI", "LHE", trip="round-trip", dep=friday, ret=friday + timedelta(days=2))  # Fri-Sun, domestic
    lahore = get(db_session)[0]
    assert {"weekend", "domestic"} <= set(lahore["categories"])
    search(db_session, "KHI", "DXB", dep=friday + timedelta(days=3), ret=None)
    assert "weekend" not in next(i for i in get(db_session) if i["destination"]["code"] == "DXB")["categories"]  # one-way
    for n in (1, 2):
        search(db_session, "KHI", "DXB", dep=friday + timedelta(days=3 + n), prices=(90 - n,), hours_ago=5 + n)
    dxb = next(i for i in get(db_session) if i["destination"]["code"] == "DXB")
    assert "flexible" in dxb["categories"] and dxb["flexibility"]["dates_observed"] == 3
    assert dxb["flexibility"]["cheapest"]["price"] == 88


def test_budget_needs_a_comparable_pool(db_session):
    for dest, price in (("DXB", 100), ("DOH", 200)):
        search(db_session, "KHI", dest, prices=(price,))
    assert not any("budget" in i["categories"] for i in get(db_session))
    search(db_session, "KHI", "LHR", prices=(300,))
    assert [i["destination"]["code"] for i in get(db_session) if "budget" in i["categories"]] == ["DXB"]


def test_deals_endpoint_filters_by_origin(client, db_session):
    search(db_session, "KHI", "DXB")
    search(db_session, "LHE", "DXB")
    body = client.get("/api/deals?origin=LHE").json()
    assert {i["origin"]["code"] for i in body["items"]} <= {"LHE"} and "not live prices" in body["basis"]
    assert client.get("/api/deals?origin=ZZZ").status_code == 404


# ------------------------------------------------------------------ popular routes

def test_personal_routes_require_sign_in_and_stay_private(client, db_session):
    assert client.get("/api/routes/popular?scope=me").status_code == 401
    me = register(client)
    other = make_client()
    other_user = register(other, email="other@example.com")
    search(db_session, "KHI", "DXB", user_id=me["id"], hours_ago=2)
    search(db_session, "KHI", "DXB", user_id=me["id"], hours_ago=1)
    search(db_session, "KHI", "IST", user_id=other_user["id"])
    mine = client.get("/api/routes/popular?scope=me").json()
    assert [(r["origin"]["code"], r["destination"]["code"], r["searches"]) for r in mine["routes"]] == [("KHI", "DXB", 2)]
    assert mine["routes"][0]["last_searched_at"] and mine["routes"][0]["last_trip"]["trip_type"] == "one-way"


def test_public_routes_are_aggregated_with_a_minimum_and_day_only(client, db_session):
    for _ in range(3):
        search(db_session, "KHI", "DXB")
    search(db_session, "KHI", "IST")  # below the minimum: hidden
    body = client.get("/api/routes/popular?scope=all").json()
    assert [(r["destination"]["code"], r["searches"]) for r in body["routes"]] == [("DXB", 3)]
    route = body["routes"][0]
    assert "last_searched_at" not in route and "last_trip" not in route and len(route["last_searched_day"]) == 10
    assert route["share"] == 100.0 and route["last_fare"]["lowest_price"] == 100


def test_saved_routes_crud_and_ownership(client, db_session):
    assert client.post("/api/account/saved-routes", json={"origin": "KHI", "destination": "DXB"}).status_code == 401
    register(client)
    assert client.post("/api/account/saved-routes", json={"origin": "KHI", "destination": "KHI"}).status_code == 422
    assert client.post("/api/account/saved-routes", json={"origin": "KHI", "destination": "ZZZ"}).status_code == 404
    saved = client.post("/api/account/saved-routes", json={"origin": "KHI", "destination": "DXB"}).json()
    client.post("/api/account/saved-routes", json={"origin": "KHI", "destination": "DXB"})  # idempotent
    assert [(r["origin"]["code"], r["destination"]["code"]) for r in saved] == [("KHI", "DXB")]
    assert len(client.get("/api/account/saved-routes").json()) == 1
    other = make_client()
    register(other, email="other@example.com")
    assert other.get("/api/account/saved-routes").json() == []
    assert client.delete("/api/account/saved-routes/KHI/DXB").json() == []
