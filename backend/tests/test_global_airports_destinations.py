from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.routes import flights as flights_routes
from app.models import FareObservation, FlightSearchHistory
from app.providers.duffel_provider import DuffelFlightProvider
from app.core.config import Settings
from app.schemas.flight import FlightSearchRequest
from app.services.airport_service import nearby_airports, search_airports
from tests.conftest import future
from tests.test_search_and_history import FakeDuffel


def codes(query: str, limit: int = 10) -> list[str]:
    return [a["code"] for a in search_airports(query, limit)]


# ------------------------------------------------------------ airport search

@pytest.mark.parametrize("query, expected", [
    ("Bangkok", ["BKK", "DMK"]),
    ("New York", ["JFK", "EWR", "LGA"]),
    ("NYC", ["JFK", "EWR", "LGA"]),
    ("dxb", ["DXB"]),
    ("Heathrow", ["LHR"]),
    ("OPKC", ["KHI"]),
])
def test_airport_search_finds_expected_airports(query, expected):
    found = codes(query)
    assert found[: len(expected)] == expected


def test_city_with_multiple_airports_lists_major_airport_first():
    london = codes("London")
    assert london[0] == "LHR"
    assert {"LGW", "STN", "LTN", "LCY"} <= set(london)


def test_search_by_country_accents_and_aliases():
    assert codes("Pakistan")[:3] == ["KHI", "LHE", "ISB"]
    assert set(codes("sao paulo")) >= {"GRU", "CGH"}
    assert "DXB" in codes("UAE")


def test_results_include_city_country_and_codes():
    bkk = search_airports("Bangkok")[0]
    assert bkk["city"] == "Bangkok" and bkk["country"] == "Thailand"
    assert bkk["name"] == "Suvarnabhumi Airport" and bkk["icao"] == "VTBS"
    assert bkk["timezone"] == "Asia/Bangkok"


def test_airport_endpoint_and_short_query(client):
    data = client.get("/api/airports?q=Bangkok").json()
    assert [a["code"] for a in data] == ["BKK", "DMK"]
    assert client.get("/api/airports?q=b").status_code == 422
    assert client.get("/api/airports?q=zzzzzz").json() == []


def test_lookup_endpoint(client):
    data = client.get("/api/airports/lookup?codes=KHI,DOH,XXX").json()
    assert [a["code"] for a in data] == ["KHI", "DOH"]
    assert client.get("/api/airports/lookup?codes=karachi").status_code == 422


# ------------------------------------------------------- current location

def test_nearby_resolves_closest_commercial_airport():
    assert nearby_airports(24.86, 67.01)[0]["code"] == "KHI"
    assert nearby_airports(25.28, 51.52)[0]["code"] == "DOH"
    assert {a["code"] for a in nearby_airports(13.75, 100.5)[:2]} == {"BKK", "DMK"}
    assert nearby_airports(0.0, -140.0) == []  # middle of the Pacific: no guess


def test_nearby_endpoint_validates_coordinates(client):
    response = client.get("/api/airports/nearby?lat=24.8607&lon=67.0011")
    assert response.status_code == 200
    first = response.json()[0]
    assert first["code"] == "KHI" and first["distance_km"] < 30
    assert client.get("/api/airports/nearby?lat=200&lon=0").status_code == 422


# ------------------------------------------------- passengers / multi-city

def test_passenger_rules():
    base = dict(origin="KHI", destination="DXB", departure_date=date.today() + timedelta(days=20), trip_type="one-way")
    FlightSearchRequest(**base, passengers=2, child_ages=[3, 7, 15], infants=2)
    with pytest.raises(ValueError, match="aged 2 to 17"):
        FlightSearchRequest(**base, passengers=1, child_ages=[1])
    with pytest.raises(ValueError, match="infants cannot outnumber adults"):
        FlightSearchRequest(**base, passengers=1, infants=2)
    with pytest.raises(ValueError, match="at most 9"):
        FlightSearchRequest(**base, passengers=5, child_ages=[5, 6, 7, 8, 9])


def test_unknown_codes_rejected():
    with pytest.raises(ValueError, match="not a recognised"):
        FlightSearchRequest(origin="KHI", destination="QQQ", departure_date=date.today(), trip_type="one-way")
    # Metro codes are accepted.
    FlightSearchRequest(origin="KHI", destination="LON", departure_date=date.today(), trip_type="one-way")


def test_duffel_payload_includes_children_infants_and_multi_city():
    provider = DuffelFlightProvider(Settings(duffel_access_token="duffel_test_x"))
    d1, d2, d3 = (date.today() + timedelta(days=n) for n in (20, 25, 30))
    request = FlightSearchRequest(
        origin="KHI", destination="KHI", departure_date=d1, trip_type="multi-city", passengers=2, child_ages=[8], infants=1,
        legs=[{"origin": "KHI", "destination": "DXB", "departure_date": d1}, {"origin": "DXB", "destination": "IST", "departure_date": d2},
              {"origin": "Istanbul (IST)", "destination": "KHI", "departure_date": d3}],
    )
    payload = provider._build_payload(request)["data"]
    assert [(s["origin"], s["destination"]) for s in payload["slices"]] == [("KHI", "DXB"), ("DXB", "IST"), ("IST", "KHI")]
    assert payload["passengers"] == [{"type": "adult"}, {"type": "adult"}, {"age": 8}, {"type": "infant_without_seat"}]


def test_multi_city_validation():
    d1 = date.today() + timedelta(days=20)
    with pytest.raises(ValueError, match="2 to 4 flights"):
        FlightSearchRequest(origin="KHI", destination="DXB", departure_date=d1, trip_type="multi-city", legs=[{"origin": "KHI", "destination": "DXB", "departure_date": d1}])
    with pytest.raises(ValueError, match="cannot depart before"):
        FlightSearchRequest(origin="KHI", destination="IST", departure_date=d1, trip_type="multi-city", legs=[
            {"origin": "KHI", "destination": "DXB", "departure_date": d1}, {"origin": "DXB", "destination": "IST", "departure_date": d1 - timedelta(days=1)}])


def test_past_dates_rejected_by_api(client):
    response = client.post("/api/flights/search", json={"origin": "KHI", "destination": "DXB", "departure_date": "2020-01-01", "trip_type": "one-way"})
    assert response.status_code == 422
    assert "past" in response.json()["detail"]


def test_multi_city_search_records_legs_without_price_observations(client, db_session, monkeypatch):
    monkeypatch.setattr(flights_routes, "get_flight_provider", lambda: (FakeDuffel([300.0]), "test"))
    body = client.post("/api/flights/search", json={
        "origin": "KHI", "destination": "IST", "departure_date": future(20), "trip_type": "multi-city", "passengers": 1,
        "legs": [{"origin": "KHI", "destination": "DXB", "departure_date": future(20)}, {"origin": "DXB", "destination": "IST", "departure_date": future(25)}],
    }).json()
    row = db_session.get(FlightSearchHistory, body["search_id"])
    assert row.trip_type == "multi-city" and [leg["destination"] for leg in row.legs] == ["DXB", "IST"]
    assert db_session.scalars(select(FareObservation)).all() == []


def test_searches_with_children_are_not_mixed_into_price_history(client, db_session, monkeypatch):
    monkeypatch.setattr(flights_routes, "get_flight_provider", lambda: (FakeDuffel([300.0]), "test"))
    client.post("/api/flights/search", json={"origin": "KHI", "destination": "DXB", "departure_date": future(20), "trip_type": "one-way", "child_ages": [6]})
    assert db_session.scalars(select(FareObservation)).all() == []
    assert db_session.scalars(select(FlightSearchHistory)).one().children == 1


# ---------------------------------------------------- destination discovery

def _observe(db, origin, dest, stops=0, connections=None, price=100.0):
    row = FlightSearchHistory(origin=origin, destination=dest, origin_code=origin, destination_code=dest, departure_date=date.today(),
                              trip_type="one-way", passengers=1, cabin="Economy", result_count=1, data_status="test")
    db.add(row)
    db.flush()
    db.add(FareObservation(search_id=row.id, provider="Duffel", data_status="test", origin_code=origin, destination_code=dest,
                           departure_date=date.today(), trip_type="one-way", cabin="Economy", passengers=1, offer_id=f"o{row.id}",
                           airline="X", price=price, currency="USD", stops=stops, connections=connections))
    db.commit()


def test_destinations_are_global_paginated_and_exclude_origin_city(client):
    data = client.get("/api/destinations?origin=KHI&page_size=10").json()
    assert data["total"] > 900
    assert len(data["items"]) == 10
    assert all(i["city"] != "Karachi" for i in data["items"])
    page2 = client.get("/api/destinations?origin=KHI&page_size=10&page=2").json()
    assert {i["key"] for i in data["items"]}.isdisjoint({i["key"] for i in page2["items"]})
    assert all(i["availability"]["status"] == "suggestion" for i in data["items"])


def test_destination_filters(client):
    beach = client.get("/api/destinations?theme=Beach&page_size=60").json()
    assert beach["items"] and all("Beach" in i["themes"] for i in beach["items"])
    europe = client.get("/api/destinations?region=Europe&page_size=60").json()
    assert all(i["region"] == "Europe" for i in europe["items"])
    thai = client.get("/api/destinations?q=thailand").json()
    assert {"Bangkok", "Phuket"} <= {i["city"] for i in thai["items"]}
    by_code = client.get("/api/destinations?q=lhr").json()
    assert by_code["items"][0]["city"] == "London"
    near = client.get("/api/destinations?origin=DOH&scope=nearby&sort=distance&page_size=5").json()
    assert near["items"][0]["distance_km"] < 600
    assert client.get("/api/destinations?theme=Party").status_code == 422


def test_destinations_change_with_origin_and_report_only_observed_routes(client, db_session):
    _observe(db_session, "KHI", "DXB", stops=0)
    _observe(db_session, "KHI", "LHR", stops=1, connections="DOH")
    from_khi = client.get("/api/destinations?origin=KHI&scope=seen").json()
    seen = {i["airport"]: i["availability"] for i in from_khi["items"]}
    assert set(seen) == {"DXB", "LHR"}
    assert seen["DXB"]["direct_seen"] is True and seen["LHR"]["direct_seen"] is False
    from_doh = client.get("/api/destinations?origin=DOH&scope=seen").json()
    assert from_doh["items"] == []


def test_route_endpoint_returns_hubs_seen_in_offers(client, db_session):
    _observe(db_session, "KHI", "LHR", stops=1, connections="DOH")
    _observe(db_session, "KHI", "LHR", stops=2, connections="DXB,IST")
    data = client.get("/api/destinations/route?origin=KHI&destination=LHR").json()
    assert {h["code"] for h in data["hubs"]} == {"DOH", "DXB", "IST"}
    assert data["distance_km"] > 6000
    assert data["latest"]["available"] is True


def test_route_daily_price_history_needs_three_days(client, db_session):
    _observe(db_session, "KHI", "DXB", price=120)
    data = client.get("/api/prices/route-history?origin=KHI&destination=DXB").json()
    assert data["groups"][0]["sufficient_for_trend"] is False


# ------------------------------------------------------------- meta / analytics

def test_meta_endpoint_reports_version(client):
    data = client.get("/api/meta").json()
    assert data["api_version"] and "auth" in data["features"] and "airports" in data["features"]


def test_public_insights_available_anonymously_and_empty(client):
    response = client.get("/api/insights/analytics?scope=all&range=7d")
    assert response.status_code == 200
    data = response.json()
    assert data["totals"]["period_searches"] == 0
    assert data["departure_months"] == [] and data["passenger_types"] == {"adults": 0, "children": 0, "infants": 0}


def test_session_restored_and_expired(client, db_session):
    from app.models import UserSession
    from tests.conftest import register

    register(client)
    assert client.get("/api/auth/me").json()["email"] == "ayesha@example.com"  # restored from cookie
    session = db_session.scalar(select(UserSession))
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    assert client.get("/api/auth/me").json() is None
    assert client.get("/api/account/profile").status_code == 401
