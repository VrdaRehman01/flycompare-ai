from datetime import date

from app.core.config import Settings
from app.providers.duffel_provider import DuffelFlightProvider
from app.schemas.flight import FlightSearchRequest


def _provider():
    return DuffelFlightProvider(
        Settings(duffel_access_token="duffel_test_unit_test_token")
    )


def _segment(origin, destination, number, depart, arrive):
    return {
        "origin": {"iata_code": origin},
        "destination": {"iata_code": destination},
        "departing_at": depart,
        "arriving_at": arrive,
        "duration": "PT2H10M",
        "marketing_carrier": {"name": "Example Air", "iata_code": "EA"},
        "operating_carrier": {"name": "Example Air"},
        "marketing_carrier_flight_number": number,
        "aircraft": {"name": "Airbus A320"},
        "passengers": [{"cabin_class": "economy"}],
    }


def test_round_trip_offer_maps_both_itineraries_and_baggage():
    provider = _provider()
    request = FlightSearchRequest(
        origin="KHI", destination="DXB", departure_date=date(2026, 11, 15),
        return_date=date(2026, 11, 22), trip_type="round-trip", passengers=1,
        cabin="Economy",
    )
    raw_offer = {
        "id": "off_test123",
        "total_amount": "114.70",
        "total_currency": "USD",
        "slices": [
            {
                "origin": {"iata_code": "KHI"},
                "destination": {"iata_code": "DXB"},
                "duration": "PT2H10M",
                "segments": [_segment("KHI", "DXB", "7426", "2026-11-15T10:50:00+05:00", "2026-11-15T12:00:00+04:00")],
            },
            {
                "origin": {"iata_code": "DXB"},
                "destination": {"iata_code": "KHI"},
                "duration": "PT2H5M",
                "segments": [_segment("DXB", "KHI", "7427", "2026-11-22T14:00:00+04:00", "2026-11-22T19:05:00+05:00")],
            },
        ],
        "passengers": [{
            "id": "pas_test",
            "type": "adult",
            "baggages": [
                {"type": "checked", "quantity": 1},
                {"type": "carry_on", "quantity": 1},
            ],
        }],
        "conditions": {
            "refund_before_departure": {"allowed": False},
            "change_before_departure": {"allowed": True, "penalty_amount": "25.00", "penalty_currency": "USD"},
        },
    }

    mapped = provider._map_offer(raw_offer, request)

    assert mapped is not None
    assert mapped.data_status == "test"
    assert mapped.price == 114.70
    assert len(mapped.itineraries) == 2
    assert mapped.itineraries[0].origin == "KHI"
    assert mapped.itineraries[1].origin == "DXB"
    assert mapped.itineraries[1].destination == "KHI"
    assert mapped.itineraries[0].segments[0].flight_number == "EA7426"
    assert len(mapped.baggage_allowances) == 2
    assert mapped.baggage_kg is None  # Quantity is not a weight; don't invent kilograms.
    assert mapped.refundable is False
    assert mapped.conditions.refund_before_departure.allowed is False
    assert mapped.conditions.change_before_departure.allowed is True
    assert mapped.conditions.change_before_departure.penalty_amount == 25.0
    assert mapped.conditions.change_before_departure.penalty_currency == "USD"


def test_one_way_offer_maps_single_itinerary():
    provider = _provider()
    request = FlightSearchRequest(
        origin="KHI", destination="DXB", departure_date=date(2026, 11, 15),
        trip_type="one-way", passengers=1, cabin="Economy",
    )
    raw_offer = {
        "id": "off_oneway",
        "total_amount": "99.00",
        "total_currency": "USD",
        "slices": [{
            "origin": {"iata_code": "KHI"},
            "destination": {"iata_code": "DXB"},
            "duration": "PT2H10M",
            "segments": [_segment("KHI", "DXB", "7426", "2026-11-15T10:50:00+05:00", "2026-11-15T12:00:00+04:00")],
        }],
        "passengers": [],
    }
    mapped = provider._map_offer(raw_offer, request)
    assert mapped is not None
    assert len(mapped.itineraries) == 1
    assert mapped.itineraries[0].destination == "DXB"
    assert mapped.conditions is None  # not supplied -> not invented
    assert mapped.refundable is None


def test_multi_segment_itinerary_counts_stops_and_keeps_connection_airport():
    provider = _provider()
    request = FlightSearchRequest(
        origin="KHI", destination="LHR", departure_date=date(2026, 11, 15),
        trip_type="one-way", passengers=2, cabin="Business",
    )
    raw_offer = {
        "id": "off_conn",
        "total_amount": "1500.00",
        "total_currency": "USD",
        "slices": [{
            "origin": {"iata_code": "KHI"},
            "destination": {"iata_code": "LHR"},
            "duration": "PT12H30M",
            "segments": [
                _segment("KHI", "DOH", "601", "2026-11-15T04:00:00+05:00", "2026-11-15T05:00:00+03:00"),
                _segment("DOH", "LHR", "007", "2026-11-15T08:00:00+03:00", "2026-11-15T13:30:00+00:00"),
            ],
        }],
        "passengers": [],
    }
    mapped = provider._map_offer(raw_offer, request)
    itinerary = mapped.itineraries[0]
    assert itinerary.stops == 1
    assert [s.destination for s in itinerary.segments] == ["DOH", "LHR"]
    assert itinerary.duration_minutes == 750
    assert mapped.cabin == "Business"


def test_payload_builds_round_trip_slices_and_passengers():
    provider = _provider()
    request = FlightSearchRequest(
        origin="Karachi (KHI)", destination="Dubai (DXB)", departure_date=date(2026, 11, 15),
        return_date=date(2026, 11, 22), trip_type="round-trip", passengers=3, cabin="Premium economy",
    )
    payload = provider._build_payload(request)["data"]
    assert [(s["origin"], s["destination"]) for s in payload["slices"]] == [("KHI", "DXB"), ("DXB", "KHI")]
    assert len(payload["passengers"]) == 3
    assert payload["cabin_class"] == "premium_economy"


def test_offer_without_price_is_dropped():
    provider = _provider()
    request = FlightSearchRequest(origin="KHI", destination="DXB", departure_date=date(2026, 11, 15), trip_type="one-way")
    raw = {"id": "x", "slices": [{"segments": [_segment("KHI", "DXB", "1", "2026-11-15T10:50:00+05:00", "2026-11-15T12:00:00+04:00")]}]}
    assert provider._map_offer(raw, request) is None


# ------------------------------------------------- fields from the documented v2 offer shape

def _documented_offer():
    """Shape from Duffel's v2 offer docs: bags live on segment passengers, flags may be strings."""
    seg = _segment("KHI", "DXB", "7426", "2026-11-15T10:50:00", "2026-11-15T12:00:00")
    seg.update({
        "id": "seg_1", "origin_terminal": "1", "destination_terminal": "3",
        "aircraft": {"name": "Airbus A320", "iata_code": "320"},
        "stops": [],
        "passengers": [{
            "passenger_id": "pas_1", "cabin_class": "economy", "cabin_class_marketing_name": "Economy Saver",
            "baggages": [{"type": "checked", "quantity": 1}, {"type": "carry_on", "quantity": 1}],
            "cabin": {"name": "economy", "marketing_name": "Economy Saver", "amenities": {
                "wifi": {"available": "true", "cost": "paid"}, "power": {"available": "false"},
                "seat": {"type": "standard", "pitch": "31", "legroom": "standard"}}},
        }],
    })
    return {
        "id": "off_documented1", "total_amount": "114.70", "total_currency": "USD",
        "base_amount": "80.00", "base_currency": "USD", "tax_amount": "34.70", "tax_currency": "USD",
        "expires_at": "2026-11-01T10:42:14.545Z", "total_emissions_kg": "212",
        "owner": {"name": "Example Air", "iata_code": "EA", "logo_symbol_url": "https://assets.duffel.com/img/airlines/for-light-background/full-color-logo/EA.svg",
                  "conditions_of_carriage_url": "https://example.com/coc"},
        "passengers": [{"id": "pas_1", "type": "adult"}],
        "slices": [{"origin": {"iata_code": "KHI"}, "destination": {"iata_code": "DXB"}, "duration": "PT2H10M",
                    "fare_brand_name": "Saver", "conditions": {"priority_boarding": "false", "advance_seat_selection": "true"},
                    "segments": [seg]}],
    }


def test_documented_offer_maps_bags_amenities_logo_and_price_breakdown():
    request = FlightSearchRequest(origin="KHI", destination="DXB", departure_date=date(2026, 11, 15), trip_type="one-way", passengers=1, cabin="Economy")
    mapped = _provider()._map_offer(_documented_offer(), request)
    assert [(b.baggage_type, b.quantity, b.slice_index, b.passenger_type) for b in mapped.baggage_allowances] == [
        ("checked", 1, 0, "adult"), ("carry_on", 1, 0, "adult")]
    assert all(b.weight is None for b in mapped.baggage_allowances)  # Duffel gives counts, not weights
    seg = mapped.itineraries[0].segments[0]
    assert (seg.aircraft, seg.aircraft_code, seg.origin_terminal, seg.cabin_marketing_name) == ("Airbus A320", "320", "1", "Economy Saver")
    assert seg.amenities.wifi.available is True and seg.amenities.wifi.cost == "paid"
    assert seg.amenities.power.available is False and seg.amenities.seat.pitch == "31"
    itin = mapped.itineraries[0]
    assert itin.fare_brand_name == "Saver" and itin.priority_boarding is False and itin.advance_seat_selection is True
    assert itin.priority_check_in is None  # not supplied stays unknown
    assert mapped.airline_logo_url.endswith("EA.svg") and mapped.airline_code == "EA"
    assert (mapped.base_amount, mapped.tax_amount, mapped.price) == (80.0, 34.7, 114.7)
    assert mapped.expires_at.year == 2026 and mapped.total_emissions_kg == 212.0


def test_missing_amenities_and_breakdown_stay_unknown():
    offer = _documented_offer()
    for key in ("base_amount", "tax_amount", "owner", "expires_at"):
        offer.pop(key)
    offer["slices"][0]["segments"][0]["passengers"][0].pop("cabin")
    offer["slices"][0]["segments"][0]["passengers"][0]["baggages"] = []
    request = FlightSearchRequest(origin="KHI", destination="DXB", departure_date=date(2026, 11, 15), trip_type="one-way", passengers=1, cabin="Economy")
    mapped = _provider()._map_offer(offer, request)
    assert mapped.itineraries[0].segments[0].amenities is None
    assert mapped.base_amount is None and mapped.tax_amount is None and mapped.airline_logo_url is None
    assert mapped.baggage_allowances == []  # no bags listed: unknown, not "zero bags" (the UI says so)


def test_seat_map_is_normalised(monkeypatch):
    provider = _provider()
    raw = [{"segment_id": "seg_1", "slice_id": "sli_1", "cabins": [{"aisles": 2, "deck": 0, "wings": {"first_row_index": 1, "last_row_index": 2}, "rows": [
        {"sections": [{"elements": [
            {"type": "seat", "designator": "1A", "name": "", "disclosures": ["No recline"],
             "available_services": [{"id": "ase_1", "passenger_id": "pas_1", "total_amount": "30.00", "total_currency": "GBP"}]},
            {"type": "seat", "designator": "1B", "available_services": []}]},
            {"elements": [{"type": "exit_row"}]}]}]}]}]
    monkeypatch.setattr(provider, "_get", lambda path, params=None: raw)
    maps = provider.seat_maps("off_abcdef123")
    first, second = maps[0]["cabins"][0]["rows"][0][0]
    assert first == {"type": "seat", "designator": "1A", "name": None, "disclosures": ["No recline"], "available": True,
                     "services": [{"id": "ase_1", "passenger_id": "pas_1", "amount": 30.0, "currency": "GBP"}]}
    assert second["available"] is False  # no purchasable service = not selectable
    assert maps[0]["cabins"][0]["rows"][0][1] == [{"type": "exit_row"}]


def test_offer_details_lists_extra_bags(monkeypatch):
    provider = _provider()
    offer = {"id": "off_abcdef123", "total_amount": "120.00", "total_currency": "USD", "passengers": [{"id": "pas_1", "type": "adult"}],
             "available_services": [
                 {"id": "ase_bag", "type": "baggage", "total_amount": "15.00", "total_currency": "USD", "maximum_quantity": 1,
                  "passenger_ids": ["pas_1"], "segment_ids": ["seg_1"],
                  "metadata": {"type": "checked", "maximum_weight_kg": 23, "maximum_length_cm": 90}},
                 {"id": "ase_cfar", "type": "cancel_for_any_reason", "total_amount": "9.00"}]}
    monkeypatch.setattr(provider, "_get", lambda path, params=None: offer)
    details = provider.offer_details("off_abcdef123")
    assert details["total_amount"] == 120.0
    assert [(b["bag_type"], b["maximum_weight_kg"], b["amount"]) for b in details["baggage_services"]] == [("checked", 23.0, 15.0)]


def test_offer_ids_are_validated():
    import pytest
    from app.providers.duffel_provider import DuffelProviderError
    with pytest.raises(DuffelProviderError):
        _provider().seat_maps("../../air/orders")


def test_demo_provider_reports_seat_maps_unsupported(client):
    body = client.get("/api/flights/offers/off_abcdef123/seat-maps").json()
    assert body["supported"] is False and "not available" in body["message"]
    assert client.get("/api/flights/offers/off_abcdef123").json()["supported"] is False
