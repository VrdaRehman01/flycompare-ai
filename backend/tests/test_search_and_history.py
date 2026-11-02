from datetime import datetime, timezone

from sqlalchemy import select

from app.api.routes import flights as flights_routes
from app.models import FareObservation, FlightSearchHistory
from app.schemas.flight import FlightItinerary, FlightOffer, FlightSegment
from tests.conftest import register
from tests.conftest import future

SEARCH = {
    "origin": "Karachi (KHI)", "destination": "Dubai (DXB)", "departure_date": future(40),
    "return_date": future(47), "trip_type": "round-trip", "passengers": 1, "cabin": "Economy",
}


class FakeDuffel:
    """Stands in for Duffel so tests never depend on live availability."""

    name = "Duffel"

    def __init__(self, prices):
        self.prices = prices

    def search(self, request):
        offers = []
        for i, price in enumerate(self.prices):
            dep = datetime(2026, 12, 10, 8 + i, 0, tzinfo=timezone.utc)
            arr = datetime(2026, 12, 10, 10 + i, 10, tzinfo=timezone.utc)
            seg = FlightSegment(airline=f"Air {i}", flight_number=f"AA{i}", origin="KHI", destination="DXB", departing_at=dep, arriving_at=arr, duration_minutes=130)
            offers.append(
                FlightOffer(
                    id=f"off_{i}", provider="Duffel", data_status="test", retrieved_at=datetime.now(timezone.utc), airline=f"Air {i % 2}",
                    flight_number=f"AA{i}", origin="KHI", destination="DXB", departure_date=dep.date(), departure_time="08:00", arrival_time="10:10",
                    duration_minutes=130, stops=0, price=price, currency="USD", cabin="Economy",
                    itineraries=[FlightItinerary(origin="KHI", destination="DXB", departing_at=dep, arriving_at=arr, duration_minutes=130, stops=0, segments=[seg])],
                )
            )
        return offers


def use_fake_duffel(monkeypatch, prices):
    monkeypatch.setattr(flights_routes, "get_flight_provider", lambda: (FakeDuffel(prices), "test"))


def test_search_requires_airport_codes(client):
    response = client.post("/api/flights/search", json={**SEARCH, "destination": "Japan"})
    assert response.status_code == 422
    same = client.post("/api/flights/search", json={**SEARCH, "destination": "KHI"})
    assert same.status_code == 422


def test_round_trip_requires_return_date(client):
    response = client.post("/api/flights/search", json={**SEARCH, "return_date": None})
    assert response.status_code == 422


def test_demo_search_is_recorded_without_price_observations(client, db_session):
    response = client.post("/api/flights/search", json=SEARCH)
    assert response.status_code == 200
    body = response.json()
    assert body["search_id"] is not None and body["data_status"] == "demo"

    row = db_session.get(FlightSearchHistory, body["search_id"])
    assert (row.origin_code, row.destination_code, row.data_status) == ("KHI", "DXB", "demo")
    assert row.user_id is None
    # Simulated prices must never become price history.
    assert db_session.scalars(select(FareObservation)).all() == []


def test_provider_search_stores_observations_and_links_user(client, db_session, monkeypatch):
    user = register(client)
    use_fake_duffel(monkeypatch, [120.0, 99.5, 140.0])
    body = client.post("/api/flights/search", json=SEARCH).json()
    assert body["data_status"] == "test"
    assert body["provider"] == "Duffel"

    row = db_session.get(FlightSearchHistory, body["search_id"])
    assert row.user_id == user["id"]
    assert (row.currency, row.min_price, row.result_count) == ("USD", 99.5, 3)

    observations = db_session.scalars(select(FareObservation)).all()
    assert sorted(o.price for o in observations) == [99.5, 120.0, 140.0]
    assert {o.data_status for o in observations} == {"test"}
    assert all(o.search_id == row.id for o in observations)


def test_provider_errors_return_502_with_message(client, monkeypatch):
    from app.providers.duffel_provider import DuffelProviderError

    class Failing:
        name = "Duffel"

        def search(self, request):
            raise DuffelProviderError("Duffel flight search timed out. Please try again.")

    monkeypatch.setattr(flights_routes, "get_flight_provider", lambda: (Failing(), "test"))
    response = client.post("/api/flights/search", json=SEARCH)
    assert response.status_code == 502
    assert "timed out" in response.json()["detail"]


def test_search_endpoint_is_rate_limited(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_search_per_minute", 2)
    assert client.post("/api/flights/search", json=SEARCH).status_code == 200
    assert client.post("/api/flights/search", json=SEARCH).status_code == 200
    assert client.post("/api/flights/search", json=SEARCH).status_code == 429


def test_airport_autocomplete_uses_local_list_without_provider(client):
    results = client.get("/api/airports?q=kara").json()
    assert results[0]["code"] == "KHI"
    assert client.get("/api/airports?q=DXB").json()[0]["city"] == "Dubai"
    assert client.get("/api/airports?q=k").status_code == 422
