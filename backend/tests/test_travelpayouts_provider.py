"""Recent fares from the Aviasales Data API (Travelpayouts), with the HTTP layer stubbed."""

from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.models import FareObservation
from app.providers import travelpayouts_provider as tp
from app.providers.factory import build_flight_provider
from app.schemas.flight import FlightSearchRequest
from tests.conftest import future

DEP = date.today() + timedelta(days=30)
RET = DEP + timedelta(days=7)
FARES = [
    {"origin_airport": "LHE", "destination_airport": "DXB", "departure_at": f"{DEP}T13:40:00+05:00", "return_at": f"{RET}T17:45:00+04:00",
     "airline": "PK", "flight_number": "203", "price": 425, "gate": "Wingie", "transfers": 0, "return_transfers": 0,
     "duration": 405, "duration_to": 230, "duration_back": 175, "link": "/search/LHE0312DXB10121?t=abc"},
    # Same itinerary again, dearer: must be dropped.
    {"origin_airport": "LHE", "destination_airport": "DXB", "departure_at": f"{DEP}T13:40:00+05:00", "return_at": f"{RET}T17:45:00+04:00",
     "airline": "PK", "flight_number": "203", "price": 442, "gate": "Other", "transfers": 0, "return_transfers": 0,
     "duration": 405, "duration_to": 230, "duration_back": 175, "link": "/search/LHE0312DXB10121?t=def"},
    {"origin_airport": "LHE", "destination_airport": "SHJ", "departure_at": f"{DEP}T02:10:00+05:00", "return_at": f"{RET}T09:00:00+04:00",
     "airline": "PA", "flight_number": "410", "price": 390, "gate": "City.Travel", "transfers": 1, "return_transfers": 0,
     "duration": 600, "duration_to": 400, "duration_back": 200, "link": "/search/x?t=ghi"},
    {"departure_at": "not-a-date", "price": 1},  # malformed rows are skipped
]


@pytest.fixture
def provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "travelpayouts_token", "tok")
    monkeypatch.setattr(settings, "travelpayouts_marker", "799772")
    tp._cache.clear()
    calls = []

    def fake_get(self, url, params=None):
        calls.append((url, params))
        if url == tp.AIRLINES_URL:
            return [{"code": "PK", "name_translations": {"en": "PIA"}}, {"code": "PA", "name": "airblue"}]
        return {"success": True, "data": FARES, "currency": "usd"}

    monkeypatch.setattr(tp.TravelpayoutsFlightProvider, "_get", fake_get)
    monkeypatch.setattr(tp, "_airline_names", None)
    p = tp.TravelpayoutsFlightProvider(settings)
    p.calls = calls
    return p


def _round_trip(adults=1, children=0, cabin="Economy"):
    return FlightSearchRequest(origin="LHE", destination="DXB", departure_date=DEP, return_date=RET, trip_type="round-trip",
                               passengers=adults, child_ages=[8] * children, cabin=cabin)


def test_fares_are_mapped_with_local_times_booking_links_and_no_duplicates(provider):
    offers = provider.search(_round_trip())
    assert [o.price for o in offers] == [390, 425]  # cheapest first; the dearer duplicate dropped
    pia = offers[1]
    assert pia.data_status == "recent" and pia.airline == "PIA" and pia.flight_number == "PK 203"
    assert pia.airline_logo_url.endswith("/PK.png") and pia.sold_by == "Wingie"
    assert pia.booking_url == "https://www.aviasales.com/search/LHE0312DXB10121?t=abc&marker=799772"
    out, back = pia.itineraries
    # 13:40 in Lahore (+05:00) plus 230 minutes lands at 16:30 Dubai time (+04:00).
    assert (out.arriving_at.hour, out.arriving_at.minute, out.arriving_at.utcoffset()) == (16, 30, timedelta(hours=4))
    assert pia.arrival_time == "16:30" and back.origin == "DXB" and back.destination == "LHE"
    # The actual airport is kept when the source returns a nearby one (Sharjah for Dubai).
    assert offers[0].destination == "SHJ" and offers[0].stops == 1


def test_totals_for_several_travellers_are_marked_as_estimates(provider):
    one = provider.search(_round_trip())[0]
    three = provider.search(_round_trip(adults=2, children=1))[0]
    assert not one.price_is_estimate
    assert three.price == one.price * 3 and three.price_is_estimate and "estimated" in three.disclaimer


def test_identical_searches_are_served_from_the_cache(provider):
    provider.search(_round_trip())
    provider.search(_round_trip())
    assert sum(1 for url, _ in provider.calls if url != tp.AIRLINES_URL) == 1


def test_unsupported_searches_are_explained(provider):
    with pytest.raises(tp.TravelpayoutsError, match="economy"):
        provider.search(_round_trip(cabin="Business"))
    legs = [{"origin": "LHE", "destination": "DXB", "departure_date": DEP.isoformat()}, {"origin": "DXB", "destination": "IST", "departure_date": RET.isoformat()}]
    multi = FlightSearchRequest(origin="LHE", destination="IST", departure_date=DEP, trip_type="multi-city", legs=legs)
    with pytest.raises(tp.TravelpayoutsError, match="Multi-city"):
        provider.search(multi)



def test_trips_longer_than_the_source_allows_pair_two_one_way_fares(provider, monkeypatch):
    back_day = DEP + timedelta(days=45)
    outbound = [{**FARES[0], "return_at": None, "price": 200, "link": "/search/out?t=1"},
                {**FARES[2], "return_at": None, "price": 150, "link": "/search/out?t=2"}]
    inbound = [{"origin_airport": "DXB", "destination_airport": "LHE", "departure_at": f"{back_day}T10:00:00+04:00", "airline": "EK",
                "flight_number": "622", "price": 180, "gate": "Emirates", "transfers": 0, "duration_to": 180, "link": "/search/back?t=3"}]

    def by_direction(self, url, params=None):
        if url == tp.AIRLINES_URL:
            return []
        # The source rejects round trips over 30 days, so only one-way queries may be sent.
        assert params["one_way"] == "true" and "return_at" not in params
        return {"success": True, "data": outbound if params["origin"] == "LHE" else inbound}

    monkeypatch.setattr(tp.TravelpayoutsFlightProvider, "_get", by_direction)
    long_trip = FlightSearchRequest(origin="LHE", destination="DXB", departure_date=DEP, return_date=back_day, trip_type="round-trip")
    offers = provider.search(long_trip)
    assert [o.price for o in offers] == [330, 380]
    cheapest = offers[0]
    assert [(i.origin, i.destination) for i in cheapest.itineraries] == [("LHE", "SHJ"), ("DXB", "LHE")]
    assert cheapest.booking_url.startswith("https://www.aviasales.com/search/out?t=2")
    assert cheapest.return_booking_url.startswith("https://www.aviasales.com/search/back?t=3")
    assert "Two separate one-way tickets" in cheapest.disclaimer and "up to 30 days" in cheapest.disclaimer
    assert cheapest.sold_by == "City.Travel + Emirates"
    # Nearby dates for long trips come from one-way fares each way (cheapest per day, summed).
    assert provider.nearby_dates(long_trip) == [{"departure_date": DEP.isoformat(), "return_date": back_day.isoformat(), "price": 330, "currency": "USD"}]


def test_round_trips_without_a_round_trip_fare_fall_back_to_two_one_ways(provider, monkeypatch):
    def one_ways_only(self, url, params=None):
        if url == tp.AIRLINES_URL:
            return []
        if params["one_way"] == "false":
            return {"success": True, "data": []}
        fare = FARES[0] if params["origin"] == "LHE" else {**FARES[0], "origin_airport": "DXB", "destination_airport": "LHE",
                                                           "departure_at": f"{RET}T10:00:00+04:00", "link": "/search/back?t=1"}
        return {"success": True, "data": [{**fare, "return_at": None}]}

    monkeypatch.setattr(tp.TravelpayoutsFlightProvider, "_get", one_ways_only)
    offers = provider.search(_round_trip())
    assert len(offers) == 1 and offers[0].price == 850 and offers[0].return_booking_url
    assert "no round-trip fare was found" in offers[0].disclaimer


def test_search_route_stores_recent_observations_and_reports_errors(client, db_session, provider, monkeypatch):
    monkeypatch.setattr(get_settings(), "flight_provider", "travelpayouts")
    body = {"origin": "LHE", "destination": "DXB", "departure_date": DEP.isoformat(), "return_date": RET.isoformat(), "trip_type": "round-trip"}
    response = client.post("/api/flights/search", json=body).json()
    assert response["data_status"] == "recent" and "not live quotes" in response["source_message"]
    assert response["results"][0]["booking_url"].endswith("marker=799772")
    assert {o.data_status for o in db_session.query(FareObservation).all()} == {"recent"}

    def rejected(self, url, params=None):
        raise tp.TravelpayoutsError("The fare source rejected the API token. Check TRAVELPAYOUTS_TOKEN.")

    monkeypatch.setattr(tp.TravelpayoutsFlightProvider, "_get", rejected)
    tp._cache.clear()
    failed = client.post("/api/flights/search", json={**body, "departure_date": future(40), "return_date": future(45)})
    assert failed.status_code == 502 and "rejected the API token" in failed.json()["detail"]


def test_nearby_dates_offer_the_cheapest_fare_per_date_pair_nearest_first(provider, monkeypatch):
    original = tp.TravelpayoutsFlightProvider._get
    # Round-trip fares only here; pairing one-way fares is covered separately.
    monkeypatch.setattr(tp.TravelpayoutsFlightProvider, "_get",
                        lambda self, url, params=None: {"data": []} if params and params["one_way"] == "true" else original(self, url, params))
    near = {**FARES[0], "departure_at": f"{DEP + timedelta(days=1)}T08:00:00+05:00", "return_at": f"{RET}T08:00:00+04:00", "price": 300}
    far = {**FARES[0], "departure_at": f"{DEP + timedelta(days=9)}T08:00:00+05:00", "return_at": f"{RET + timedelta(days=9)}T08:00:00+04:00", "price": 99}
    past = {**FARES[0], "departure_at": "2020-01-01T08:00:00+05:00", "return_at": "2020-01-05T08:00:00+04:00", "price": 1}
    FARES.extend([near, far, past])
    try:
        dates = provider.nearby_dates(_round_trip())
    finally:
        del FARES[-3:]
    assert [(d["departure_date"], d["return_date"], d["price"]) for d in dates] == [
        (DEP.isoformat(), RET.isoformat(), 390),  # the exact pair, cheapest of its fares
        ((DEP + timedelta(days=1)).isoformat(), RET.isoformat(), 300),
        ((DEP + timedelta(days=9)).isoformat(), (RET + timedelta(days=9)).isoformat(), 99),
    ]
    month_query = provider.calls[-1][1]
    assert month_query["departure_at"] == DEP.strftime("%Y-%m") and month_query["return_at"] == RET.strftime("%Y-%m")
    assert provider.nearby_dates(_round_trip(cabin="Business")) == []


def test_empty_exact_dates_suggest_nearby_dates(client, provider, monkeypatch):
    monkeypatch.setattr(get_settings(), "flight_provider", "travelpayouts")

    def month_only(self, url, params=None):
        if url == tp.AIRLINES_URL:
            return []
        exact = len(params["departure_at"]) == 10
        return {"success": True, "data": [] if exact else FARES[:1]}

    monkeypatch.setattr(tp.TravelpayoutsFlightProvider, "_get", month_only)
    body = {"origin": "LHE", "destination": "DXB", "departure_date": future(50), "return_date": future(55), "trip_type": "round-trip"}
    response = client.post("/api/flights/search", json=body).json()
    assert response["results"] == []
    assert response["nearby_dates"] == [{"departure_date": DEP.isoformat(), "return_date": RET.isoformat(), "price": 425.0, "currency": "USD"}]


def test_recent_fares_count_as_real_data_in_production(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "flight_provider", "travelpayouts")
    monkeypatch.setattr(settings, "travelpayouts_token", "tok")
    monkeypatch.setattr(settings, "app_env", "production")
    assert build_flight_provider(settings)[1] == "recent"
