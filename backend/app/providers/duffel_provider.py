import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.errors import FlightProviderError
from app.schemas.flight import (
    Amenity,
    BaggageAllowance,
    CabinAmenities,
    FareCondition,
    FareConditions,
    FlightItinerary,
    FlightOffer,
    FlightSearchRequest,
    FlightSegment,
    SeatInfo,
)

OFFER_ID = re.compile(r"^off_[A-Za-z0-9]{6,64}$")


def _tri_state(value: Any) -> bool | None:
    """Duffel sends some flags as booleans and others as "true"/"false" strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return None


def _text(value: Any) -> str | None:
    """Provider text with placeholders such as "n/a" treated as not supplied."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in {"", "n/a", "na", "none", "unknown"} else text


def _amount(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class DuffelProviderError(FlightProviderError):
    """Raised when Duffel cannot return a usable flight search."""


class DuffelFlightProvider:
    name = "Duffel"

    CABIN_MAP = {
        "Economy": "economy",
        "Premium economy": "premium_economy",
        "Business": "business",
        "First class": "first",
    }

    def __init__(self, settings: Settings):
        token = (settings.duffel_access_token or "").strip()
        if not token:
            raise DuffelProviderError(
                "Duffel is selected but DUFFEL_ACCESS_TOKEN is not configured."
            )
        self.token = token
        self.base_url = settings.duffel_api_url.rstrip("/")
        self.api_version = settings.duffel_api_version
        self.timeout = settings.duffel_timeout_seconds
        self.data_status = "test" if token.startswith("duffel_test_") else "live"

    @staticmethod
    def _airport_code(value: str) -> str:
        match = re.search(r"\(([A-Za-z]{3})\)", value)
        code = match.group(1) if match else value.strip()
        if not re.fullmatch(r"[A-Za-z]{3}", code):
            raise DuffelProviderError(
                f"'{value}' must contain a three-letter airport IATA code, "
                "for example Karachi (KHI)."
            )
        return code.upper()

    @staticmethod
    def _duration_minutes(value: str | None) -> int | None:
        if not value:
            return None
        match = re.fullmatch(
            r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?",
            value,
        )
        if not match:
            return None
        days, hours, minutes, seconds = match.groups()
        return (
            int(days or 0) * 1440
            + int(hours or 0) * 60
            + int(minutes or 0)
            + round(float(seconds or 0) / 60)
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @classmethod
    def _map_itinerary(cls, slice_data: dict[str, Any]) -> FlightItinerary | None:
        segments = slice_data.get("segments") or []
        if not segments:
            return None
        mapped_segments: list[FlightSegment] = []
        for segment in segments:
            departing_at = segment.get("departing_at")
            arriving_at = segment.get("arriving_at")
            if not departing_at or not arriving_at:
                continue
            marketing = segment.get("marketing_carrier") or {}
            operating = segment.get("operating_carrier") or {}
            flight_number = segment.get("marketing_carrier_flight_number")
            aircraft = segment.get("aircraft") or {}
            seg_passenger = (segment.get("passengers") or [{}])[0] or {}
            mapped_segments.append(
                FlightSegment(
                    id=segment.get("id"),
                    airline=operating.get("name") or marketing.get("name"),
                    airline_code=marketing.get("iata_code") or operating.get("iata_code"),
                    operating_airline=operating.get("name"),
                    marketing_airline=marketing.get("name"),
                    flight_number=(
                        f"{marketing.get('iata_code', '')}{flight_number}"
                        if flight_number else None
                    ),
                    origin=(segment.get("origin") or {}).get("iata_code", ""),
                    destination=(segment.get("destination") or {}).get("iata_code", ""),
                    origin_terminal=segment.get("origin_terminal"),
                    destination_terminal=segment.get("destination_terminal"),
                    departing_at=cls._parse_datetime(departing_at),
                    arriving_at=cls._parse_datetime(arriving_at),
                    duration_minutes=cls._duration_minutes(segment.get("duration")),
                    aircraft=aircraft.get("name"),
                    aircraft_code=aircraft.get("iata_code"),
                    cabin=seg_passenger.get("cabin_class"),
                    cabin_marketing_name=seg_passenger.get("cabin_class_marketing_name")
                    or (seg_passenger.get("cabin") or {}).get("marketing_name"),
                    amenities=cls._amenities(seg_passenger.get("cabin")),
                    technical_stops=[
                        (stop.get("airport") or {}).get("iata_code")
                        for stop in segment.get("stops") or []
                        if (stop.get("airport") or {}).get("iata_code")
                    ],
                )
            )
        if not mapped_segments:
            return None
        first, last = mapped_segments[0], mapped_segments[-1]
        origin = (slice_data.get("origin") or {}).get("iata_code") or first.origin
        destination = (slice_data.get("destination") or {}).get("iata_code") or last.destination
        perks = slice_data.get("conditions") or {}
        return FlightItinerary(
            origin=origin,
            destination=destination,
            departing_at=first.departing_at,
            arriving_at=last.arriving_at,
            duration_minutes=cls._duration_minutes(slice_data.get("duration")),
            stops=max(0, len(mapped_segments) - 1),
            segments=mapped_segments,
            fare_brand_name=slice_data.get("fare_brand_name"),
            priority_check_in=_tri_state(perks.get("priority_check_in")),
            priority_boarding=_tri_state(perks.get("priority_boarding")),
            advance_seat_selection=_tri_state(perks.get("advance_seat_selection")),
        )

    @staticmethod
    def _amenities(cabin: dict[str, Any] | None) -> CabinAmenities | None:
        raw = (cabin or {}).get("amenities")
        if not isinstance(raw, dict):
            return None
        wifi, power, seat = raw.get("wifi"), raw.get("power"), raw.get("seat")
        return CabinAmenities(
            wifi=Amenity(available=_tri_state(wifi.get("available")), cost=wifi.get("cost")) if isinstance(wifi, dict) else None,
            power=Amenity(available=_tri_state(power.get("available"))) if isinstance(power, dict) else None,
            seat=SeatInfo(
                type=_text(seat.get("type")),
                pitch=_text(seat.get("pitch")),
                legroom=_text(seat.get("legroom")),
            ) if isinstance(seat, dict) else None,
        )

    @staticmethod
    def _map_baggage(offer: dict[str, Any]) -> list[BaggageAllowance]:
        """Included bags per itinerary and passenger.

        Duffel lists them on ``slices[].segments[].passengers[].baggages`` (a bag is
        checked through the slice, so the first segment is used). Responses with
        ``offer.passengers[].baggages`` are still understood.
        """
        passenger_type = {
            p.get("id"): p.get("type") or ("child" if p.get("age") is not None and p.get("age") < 18 else None)
            for p in offer.get("passengers") or []
        }
        allowances: list[BaggageAllowance] = []
        for slice_index, slice_data in enumerate(offer.get("slices") or []):
            first_segment = (slice_data.get("segments") or [{}])[0] or {}
            for passenger in first_segment.get("passengers") or []:
                for baggage in passenger.get("baggages") or []:
                    allowances.append(BaggageAllowance(
                        passenger_id=passenger.get("passenger_id"),
                        passenger_type=passenger_type.get(passenger.get("passenger_id")),
                        baggage_type=baggage.get("type", "unknown"),
                        quantity=baggage.get("quantity"),
                        slice_index=slice_index,
                    ))
        if allowances:
            return allowances
        for passenger in offer.get("passengers") or []:
            for baggage in passenger.get("baggages") or []:
                allowances.append(
                    BaggageAllowance(
                        passenger_id=passenger.get("id"),
                        passenger_type=passenger.get("type"),
                        baggage_type=baggage.get("type", "unknown"),
                        quantity=baggage.get("quantity"),
                        weight=baggage.get("weight"),
                        weight_unit=baggage.get("weight_unit"),
                    )
                )
        return allowances

    @staticmethod
    def _refundable(offer: dict[str, Any]) -> bool | None:
        conditions = offer.get("conditions") or {}
        refund = conditions.get("refund_before_departure") or {}
        allowed = refund.get("allowed")
        return allowed if isinstance(allowed, bool) else None

    @staticmethod
    def _conditions(offer: dict[str, Any]) -> FareConditions | None:
        raw = offer.get("conditions")
        if not isinstance(raw, dict):
            return None

        def one(key: str) -> FareCondition | None:
            item = raw.get(key)
            if not isinstance(item, dict):
                return None
            amount = item.get("penalty_amount")
            try:
                amount = float(amount) if amount is not None else None
            except (TypeError, ValueError):
                amount = None
            allowed = item.get("allowed")
            return FareCondition(
                allowed=allowed if isinstance(allowed, bool) else None,
                penalty_amount=amount,
                penalty_currency=item.get("penalty_currency"),
            )

        conditions = FareConditions(
            refund_before_departure=one("refund_before_departure"),
            change_before_departure=one("change_before_departure"),
        )
        if conditions.refund_before_departure is None and conditions.change_before_departure is None:
            return None
        return conditions

    def _build_payload(self, request: FlightSearchRequest) -> dict:
        if request.trip_type == "multi-city" and request.legs:
            slices = [
                {
                    "origin": self._airport_code(leg.origin),
                    "destination": self._airport_code(leg.destination),
                    "departure_date": leg.departure_date.isoformat(),
                }
                for leg in request.legs
            ]
        else:
            origin = self._airport_code(request.origin)
            destination = self._airport_code(request.destination)
            slices = [{
                "origin": origin,
                "destination": destination,
                "departure_date": request.departure_date.isoformat(),
            }]
            if request.trip_type == "round-trip" and request.return_date:
                slices.append({
                    "origin": destination,
                    "destination": origin,
                    "departure_date": request.return_date.isoformat(),
                })
        passengers = (
            [{"type": "adult"} for _ in range(request.passengers)]
            # Duffel: passengers under 18 are identified by age rather than a type.
            + [{"age": age} for age in request.child_ages]
            + [{"type": "infant_without_seat"} for _ in range(request.infants)]
        )
        return {
            "data": {
                "slices": slices,
                "passengers": passengers,
                "cabin_class": self.CABIN_MAP[request.cabin],
                "max_connections": 2,
            }
        }

    def _map_offer(self, offer: dict[str, Any], request: FlightSearchRequest) -> FlightOffer | None:
        raw_slices = offer.get("slices") or []
        if not raw_slices:
            return None
        itineraries = [
            itinerary
            for slice_data in raw_slices
            if (itinerary := self._map_itinerary(slice_data)) is not None
        ]
        if not itineraries:
            return None

        outbound = itineraries[0]
        first_segment = outbound.segments[0]
        marketing = (raw_slices[0].get("segments") or [{}])[0].get("marketing_carrier") or {}
        airline = first_segment.airline or marketing.get("name") or "Airline not supplied"
        flight_number = first_segment.flight_number or "See itinerary"
        total_amount = offer.get("total_amount")
        if total_amount is None:
            return None
        try:
            price = float(total_amount)
        except (TypeError, ValueError):
            return None

        baggage = self._map_baggage(offer)
        owner = offer.get("owner") or {}
        try:
            expires = self._parse_datetime(offer["expires_at"]) if offer.get("expires_at") else None
        except ValueError:
            expires = None
        # Keep the old summary fields for existing clients while adding complete itineraries.
        return FlightOffer(
            id=offer.get("id", "unknown"),
            provider=self.name,
            data_status=self.data_status,
            retrieved_at=datetime.now(timezone.utc),
            airline=airline,
            flight_number=flight_number,
            origin=outbound.origin,
            destination=outbound.destination,
            departure_date=outbound.departing_at.date(),
            departure_time=outbound.departing_at.strftime("%H:%M"),
            arrival_time=outbound.arriving_at.strftime("%H:%M"),
            duration_minutes=outbound.duration_minutes or 0,
            stops=outbound.stops,
            price=price,
            currency=offer.get("total_currency") or "USD",
            baggage_kg=None,
            cabin=request.cabin,
            refundable=self._refundable(offer),
            disclaimer=(
                "Duffel test-environment offer. Not a live bookable fare."
                if self.data_status == "test"
                else "Live Duffel offer. Price and availability can change; revalidate before booking."
            ),
            itineraries=itineraries,
            baggage_allowances=baggage,
            conditions=self._conditions(offer),
            airline_code=owner.get("iata_code") or first_segment.airline_code,
            airline_logo_url=owner.get("logo_symbol_url") or marketing.get("logo_symbol_url"),
            conditions_of_carriage_url=owner.get("conditions_of_carriage_url"),
            base_amount=_amount(offer.get("base_amount")),
            base_currency=offer.get("base_currency"),
            tax_amount=_amount(offer.get("tax_amount")),
            tax_currency=offer.get("tax_currency"),
            expires_at=expires,
            total_emissions_kg=_amount(offer.get("total_emissions_kg")),
            passenger_count=len(offer.get("passengers") or []) or None,
            supports_seat_maps=True,
            supports_extra_services=True,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": self.api_version,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def place_suggestions(self, query: str) -> list[dict[str, str]]:
        """Airport suggestions from Duffel's Places API (airports only)."""
        try:
            with httpx.Client(timeout=min(self.timeout, 10.0)) as client:
                response = client.get(
                    f"{self.base_url}/places/suggestions",
                    headers=self._headers(),
                    params={"query": query},
                )
                response.raise_for_status()
                data = response.json().get("data", [])
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise DuffelProviderError("Airport suggestions are unavailable right now.") from exc
        places: list[dict[str, str]] = []
        for place in data:
            if place.get("type") != "airport" or not place.get("iata_code"):
                continue
            places.append({
                "code": place["iata_code"],
                "name": place.get("name") or place["iata_code"],
                "city": place.get("city_name") or (place.get("city") or {}).get("name") or "",
                "country": place.get("iata_country_code") or "",
            })
        return places

    def _get(self, path: str, params: dict | None = None) -> Any:
        try:
            with httpx.Client(timeout=min(self.timeout, 20.0)) as client:
                response = client.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
        except httpx.TimeoutException as exc:
            raise DuffelProviderError("Duffel did not respond in time. Please try again.") from exc
        except httpx.RequestError as exc:
            raise DuffelProviderError("Could not connect to Duffel.") from exc
        if response.status_code == 404:
            raise DuffelProviderError("This offer is no longer available. Search again for current prices.")
        if response.status_code >= 400:
            try:
                message = response.json()["errors"][0]["message"]
            except (ValueError, KeyError, IndexError, TypeError):
                message = "Duffel API request failed."
            raise DuffelProviderError(f"Duffel returned HTTP {response.status_code}: {message}")
        try:
            return response.json().get("data")
        except (ValueError, AttributeError) as exc:
            raise DuffelProviderError("Duffel returned an unexpected response.") from exc

    @staticmethod
    def _seat_element(element: dict[str, Any]) -> dict[str, Any]:
        kind = element.get("type") or "empty"
        if kind != "seat":
            return {"type": kind}
        services = [
            {"id": svc.get("id"), "passenger_id": svc.get("passenger_id"),
             "amount": _amount(svc.get("total_amount")), "currency": svc.get("total_currency")}
            for svc in element.get("available_services") or []
        ]
        return {
            "type": "seat",
            "designator": element.get("designator"),
            "name": element.get("name") or None,
            "disclosures": [d for d in element.get("disclosures") or [] if isinstance(d, str)],
            # Duffel: a seat without available services cannot be selected.
            "available": bool(services),
            "services": services,
        }

    def seat_maps(self, offer_id: str) -> list[dict[str, Any]]:
        """Seat maps per segment, normalised. Empty when the airline supplies none."""
        if not OFFER_ID.match(offer_id):
            raise DuffelProviderError("Invalid offer id.")
        return [
            {
                "segment_id": seat_map.get("segment_id"),
                "slice_id": seat_map.get("slice_id"),
                "cabins": [
                    {
                        "cabin_class": cabin.get("cabin_class"),
                        "deck": cabin.get("deck"),
                        "aisles": cabin.get("aisles"),
                        "wings": cabin.get("wings"),
                        "rows": [
                            [[self._seat_element(e) for e in section.get("elements") or []] for section in row.get("sections") or []]
                            for row in cabin.get("rows") or []
                        ],
                    }
                    for cabin in seat_map.get("cabins") or []
                ],
            }
            for seat_map in self._get("/air/seat_maps", {"offer_id": offer_id}) or []
        ]

    def offer_details(self, offer_id: str) -> dict[str, Any]:
        """Re-fetch an offer: current price and expiry, passengers and purchasable extra bags."""
        if not OFFER_ID.match(offer_id):
            raise DuffelProviderError("Invalid offer id.")
        offer = self._get(f"/air/offers/{offer_id}", {"return_available_services": "true"}) or {}
        bags = []
        for svc in offer.get("available_services") or []:
            if svc.get("type") != "baggage":
                continue
            meta = svc.get("metadata") or {}
            bags.append({
                "id": svc.get("id"),
                "bag_type": meta.get("type"),
                "maximum_weight_kg": _amount(meta.get("maximum_weight_kg")),
                "maximum_length_cm": _amount(meta.get("maximum_length_cm")),
                "maximum_height_cm": _amount(meta.get("maximum_height_cm")),
                "maximum_depth_cm": _amount(meta.get("maximum_depth_cm")),
                "amount": _amount(svc.get("total_amount")),
                "currency": svc.get("total_currency"),
                "maximum_quantity": svc.get("maximum_quantity"),
                "passenger_ids": svc.get("passenger_ids") or [],
                "segment_ids": svc.get("segment_ids") or [],
            })
        payment = offer.get("payment_requirements") or {}
        return {
            "offer_id": offer.get("id") or offer_id,
            "total_amount": _amount(offer.get("total_amount")),
            "total_currency": offer.get("total_currency"),
            "base_amount": _amount(offer.get("base_amount")),
            "tax_amount": _amount(offer.get("tax_amount")),
            "tax_currency": offer.get("tax_currency"),
            "expires_at": offer.get("expires_at"),
            "price_guarantee_expires_at": payment.get("price_guarantee_expires_at"),
            "passengers": [
                {"id": p.get("id"), "type": p.get("type") or ("child" if p.get("age") is not None else None), "age": p.get("age")}
                for p in offer.get("passengers") or []
            ],
            "baggage_services": bags,
            "conditions_of_carriage_url": (offer.get("owner") or {}).get("conditions_of_carriage_url"),
        }

    def search(self, request: FlightSearchRequest) -> list[FlightOffer]:
        url = f"{self.base_url}/air/offer_requests"
        headers = self._headers()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=self._build_payload(request),
                    params={"return_offers": "true"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise DuffelProviderError("Duffel flight search timed out. Please try again.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            try:
                errors = exc.response.json().get("errors", [])
                message = errors[0].get("message", "Duffel API request failed.")
            except (ValueError, IndexError, AttributeError):
                message = "Duffel API request failed."
            raise DuffelProviderError(f"Duffel returned HTTP {status}: {message}") from exc
        except httpx.RequestError as exc:
            raise DuffelProviderError(
                "Could not connect to Duffel. Check your internet connection."
            ) from exc

        try:
            raw_offers = response.json().get("data", {}).get("offers", [])
        except (ValueError, AttributeError) as exc:
            raise DuffelProviderError("Duffel returned an unexpected response.") from exc
        return [
            mapped
            for raw_offer in raw_offers
            if (mapped := self._map_offer(raw_offer, request)) is not None
        ]
