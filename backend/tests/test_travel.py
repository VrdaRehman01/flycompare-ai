from datetime import date, timedelta

import httpx
import pytest

from app.core.config import get_settings
from app.data.travel_content import GUIDES
from app.providers import stays_provider
from app.providers.stays_provider import DuffelStaysProvider
from app.services import guide_service, planner_service
from app.services.travel_common import LocationNotFound, resolve_city
from tests.conftest import future


# ------------------------------------------------------------------ locations

def test_every_guide_city_exists_in_the_destination_dataset():
    for key in GUIDES:
        assert resolve_city(key).key == key


def test_locations_resolve_from_airport_and_metro_codes():
    assert resolve_city("DXB").key == "Dubai|AE"
    assert resolve_city("lhr").key == "London|GB"
    assert resolve_city("LON").key == "London|GB"
    with pytest.raises(LocationNotFound):
        resolve_city("ZZZ")


# ---------------------------------------------------------------------- stays

def test_demo_stays_are_labelled_deterministic_and_priced_per_night(client):
    params = {"location": "DXB", "check_in": future(20), "check_out": future(23), "adults": 2, "rooms": 1}
    first = client.get("/api/stays/search", params=params).json()
    assert first["data_status"] == "demo" and "simulated" in first["notice"]
    assert first["nights"] == 3 and first["city"]["key"] == "Dubai|AE"
    assert {r["property_type"] for r in first["results"]} >= {"hotel", "apartment", "hostel"}
    for r in first["results"]:
        assert r["total_price"] == pytest.approx(r["nightly_price"] * 3, abs=1)
    assert client.get("/api/stays/search", params=params).json()["results"] == first["results"]


def test_stays_validate_dates_and_rooms(client):
    base = {"location": "DXB", "check_in": future(10), "check_out": future(12)}
    assert client.get("/api/stays/search", params={**base, "check_out": future(10)}).status_code == 422
    assert client.get("/api/stays/search", params={**base, "check_in": (date.today() - timedelta(days=1)).isoformat()}).status_code == 422
    assert client.get("/api/stays/search", params={**base, "adults": 1, "rooms": 2}).status_code == 422
    assert client.get("/api/stays/search", params={**base, "location": "ZZZ"}).status_code == 404


class _Forbidden:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, *a, **k):
        return httpx.Response(403, json={"errors": [{"message": "forbidden"}]})


def test_stays_fall_back_to_demo_when_duffel_stays_is_not_enabled(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "stays_provider", "duffel")
    monkeypatch.setattr(settings, "duffel_access_token", "duffel_test_x")
    monkeypatch.setattr(stays_provider.httpx, "Client", _Forbidden)
    body = client.get("/api/stays/search", params={"location": "LHR", "check_in": future(30), "check_out": future(32)}).json()
    assert body["data_status"] == "demo"
    assert "not enabled" in body["notice"] and body["results"]


def test_duffel_stay_results_are_mapped():
    city = resolve_city("LHR")
    mapped = DuffelStaysProvider._map({
        "id": "srr_1", "cheapest_rate_total_amount": "300.00", "cheapest_rate_currency": "GBP",
        "accommodation": {"name": "Test Hotel", "rating": 4, "review_score": 8.7, "photos": [{"url": "https://x/p.jpg"}],
                          "amenities": [{"type": "wifi"}, {"type": "pool"}],
                          "location": {"geographic_coordinates": {"latitude": city.lat, "longitude": city.lon}, "address": {"line_one": "1 Road", "city_name": "London"}}},
    }, city, 3)
    assert mapped["nightly_price"] == 100 and mapped["currency"] == "GBP" and mapped["stars"] == 4
    assert mapped["amenities"] == ["Free Wi-Fi", "Pool"]
    assert mapped["distance_km"] > 15  # measured from central London, and these coordinates are Heathrow's
    assert DuffelStaysProvider._map({"accommodation": {}}, city, 3) is None


# ----------------------------------------------------------- cars & transfers

def test_car_rental_days_and_driver_fees(client):
    base = {"location": "DXB", "pickup_date": future(5), "dropoff_date": future(8), "pickup_time": "10:00", "dropoff_time": "11:00"}
    adult = client.get("/api/cars/search", params=base).json()
    assert adult["rental_days"] == 4  # 3 days and 1 hour = 4 started days
    young = client.get("/api/cars/search", params={**base, "driver_age": 21}).json()
    assert all(y["driver_fees"] > 0 for y in young["results"])
    assert young["results"][0]["total_price"] > adult["results"][0]["total_price"]
    same_day = client.get("/api/cars/search", params={**base, "dropoff_date": future(5), "dropoff_time": "18:00"})
    assert same_day.status_code == 200 and same_day.json()["rental_days"] == 1
    assert client.get("/api/cars/search", params={**base, "dropoff_date": future(4)}).status_code == 422


def test_transfers_respect_vehicle_capacity(client):
    small = client.get("/api/transfers/search", params={"location": "IST", "date": future(3), "passengers": 2, "bags": 2}).json()
    big = client.get("/api/transfers/search", params={"location": "IST", "date": future(3), "passengers": 6, "bags": 6}).json()
    assert "Private sedan" in {o["vehicle"] for o in small["results"]}
    assert "Private sedan" not in {o["vehicle"] for o in big["results"]}
    assert all(o["max_passengers"] is None or o["max_passengers"] >= 6 for o in big["results"])
    # Istanbul Airport is ~35 km in a straight line from the historic centre, not at it.
    assert 35 <= small["distance_km"] <= 60 and small["data_status"] == "demo"


# ---------------------------------------------------------------------- tours

def test_group_tours_price_per_person_and_private_per_party(client):
    group = client.get("/api/tours/search", params={"location": "Paris|FR", "date": future(9), "travellers": 4, "kind": "group"}).json()
    private2 = client.get("/api/tours/search", params={"location": "Paris|FR", "date": future(9), "travellers": 2, "kind": "private"}).json()
    private6 = client.get("/api/tours/search", params={"location": "Paris|FR", "date": future(9), "travellers": 6, "kind": "private"}).json()
    assert group["results"] and all(t["price_basis"] == "per person" for t in group["results"])
    t = group["results"][0]
    assert t["total_price"] == pytest.approx(t["price_per_person"] * 4, abs=0.05)
    sights = {s.name for s in GUIDES["Paris|FR"].sights}
    assert all(stop["name"] in sights for tour in group["results"] for stop in tour["stops"])
    per_head = {r["title"]: r["price_per_person"] for r in private2["results"]}
    assert any(r["price_per_person"] < per_head[r["title"]] for r in private6["results"] if r["title"] in per_head)


def test_tours_are_empty_with_a_notice_for_cities_without_a_guide(client):
    body = client.get("/api/tours/search", params={"location": "ANC", "date": future(9)}).json()
    assert body["results"] == [] and "No tours" in body["notice"]


# --------------------------------------------------------------------- guides

def test_guides_list_and_offline_detail(client):
    items = client.get("/api/guides").json()["items"]
    assert len(items) == len(GUIDES)
    detail = client.get("/api/guides/detail", params={"location": "IST"}).json()
    assert detail["curated"] and detail["sights"] and detail["areas"]
    assert detail["climate"] is None and detail["overview"] is None  # external data disabled in tests


def test_climate_is_aggregated_per_month_and_best_months_ranked():
    days = []
    d = date(2025, 1, 1)
    while d.year == 2025:
        days.append(d)
        d += timedelta(days=1)
    hot = {6, 7, 8}
    daily = {
        "time": [x.isoformat() for x in days],
        "temperature_2m_max": [40.0 if x.month in hot else 24.0 if x.month in (3, 4, 11) else 30.0 for x in days],
        "temperature_2m_min": [20.0 for _ in days],
        "precipitation_sum": [5.0 if x.month == 11 and x.day <= 20 else 0.0 for x in days],
    }
    out = guide_service.aggregate_climate(daily, 2025)
    assert out["months"][0]["avg_high_c"] == 30.0 and out["months"][2]["avg_high_c"] == 24.0
    assert out["months"][10]["rainy_days"] == 20
    assert out["best_months"][:2] == ["Mar", "Apr"]
    assert set(out["avoid_months"]) <= {"Jun", "Jul", "Aug"}


# -------------------------------------------------------------------- planner

def test_planner_builds_one_day_per_date_without_repeating_sights(client):
    body = {"location": "DXB", "start": future(40), "end": future(44), "travellers": 2, "interests": ["Adventure", "Food"], "pace": "balanced", "budget": "mid"}
    plan = client.post("/api/planner/plan", json=body).json()
    assert len(plan["days"]) == 5 and plan["days"][0]["kind"] == "arrival" and plan["days"][-1]["kind"] == "departure"
    sights = [i["title"] for d in plan["days"] for i in d["items"] if i["kind"] == "sight"]
    assert len(sights) == len(set(sights))
    assert "Desert safari" in sights  # matches the Adventure interest
    assert plan["costs"]["total"] == sum(line["amount"] for line in plan["costs"]["lines"])


def test_planner_interests_change_the_plan():
    city = resolve_city("DXB")
    start = date.today() + timedelta(days=60)
    food = planner_service.plan_trip(city, start, start + timedelta(days=4), 2, ["Food", "Shopping"], "balanced", "mid")
    adventure = planner_service.plan_trip(city, start, start + timedelta(days=4), 2, ["Adventure", "Beach"], "balanced", "mid")
    titles = lambda p: [i["title"] for d in p["days"] for i in d["items"] if i["kind"] in ("sight", "free")]  # noqa: E731
    assert titles(food) != titles(adventure)
    assert "Desert safari" in titles(adventure) and "Desert safari" not in titles(food)
    assert any("Food crawl" in t or "Shopping in" in t for t in titles(food))


def test_planner_handles_cities_without_a_guide_and_validates_length(client):
    plan = client.post("/api/planner/plan", json={"location": "ANC", "start": future(10), "end": future(12)}).json()
    assert not plan["curated"] and plan["note"] and len(plan["days"]) == 3
    assert client.post("/api/planner/plan", json={"location": "DXB", "start": future(10), "end": future(40)}).status_code == 422


def test_relaxed_pace_schedules_fewer_sights_than_packed():
    city = resolve_city("Rome|IT")
    start = date.today() + timedelta(days=60)
    relaxed = planner_service.plan_trip(city, start, start + timedelta(days=3), 2, [], "relaxed", "mid")
    packed = planner_service.plan_trip(city, start, start + timedelta(days=3), 2, [], "packed", "mid")
    count = lambda p: sum(1 for d in p["days"] for i in d["items"] if i["kind"] == "sight")  # noqa: E731
    assert count(relaxed) < count(packed)
