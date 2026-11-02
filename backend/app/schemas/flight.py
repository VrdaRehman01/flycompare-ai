import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_CODE_IN_LABEL = re.compile(r"\(([A-Za-z]{3})\)\s*$")


def airport_code_from(value: str) -> str | None:
    """Extract an IATA code from "KHI" or "Karachi (KHI)"; None for free text."""
    value = value.strip()
    if re.fullmatch(r"[A-Za-z]{3}", value):
        return value.upper()
    match = _CODE_IN_LABEL.search(value)
    return match.group(1).upper() if match else None


MAX_SEATS = 9  # Duffel accepts at most 9 seated passengers per offer request
MAX_MULTI_CITY_LEGS = 4


class SearchLeg(BaseModel):
    origin: str = Field(min_length=3, max_length=100)
    destination: str = Field(min_length=3, max_length=100)
    departure_date: date

    @field_validator("origin", "destination")
    @classmethod
    def require_airport_code(cls, value: str) -> str:
        return _validated_location(value)

    @property
    def origin_code(self) -> str:
        return airport_code_from(self.origin) or ""

    @property
    def destination_code(self) -> str:
        return airport_code_from(self.destination) or ""


def _validated_location(value: str) -> str:
    from app.services.airport_service import is_known_location

    code = airport_code_from(value)
    if code is None:
        raise ValueError("Choose an airport from the list, for example Karachi (KHI).")
    if not is_known_location(code):
        raise ValueError(f"'{code}' is not a recognised airport or city code.")
    return value.strip()


class FlightSearchRequest(BaseModel):
    origin: str = Field(min_length=3, max_length=100)
    destination: str = Field(min_length=3, max_length=100)
    departure_date: date
    return_date: date | None = None
    trip_type: Literal["round-trip", "one-way", "multi-city"] = "round-trip"
    passengers: int = Field(default=1, ge=1, le=9, description="Number of adults (18+).")
    child_ages: list[int] = Field(default_factory=list, max_length=8, description="Age (2–17) of each child; children have their own seat.")
    infants: int = Field(default=0, ge=0, le=9, description="Infants under 2 (on an adult's lap).")
    cabin: Literal["Economy", "Premium economy", "Business", "First class"] = "Economy"
    legs: list[SearchLeg] | None = Field(default=None, description="Multi-city flights, in travel order.")

    @field_validator("origin", "destination")
    @classmethod
    def require_airport_code(cls, value: str) -> str:
        return _validated_location(value)

    @property
    def origin_code(self) -> str:
        return airport_code_from(self.origin) or ""

    @property
    def destination_code(self) -> str:
        return airport_code_from(self.destination) or ""

    @property
    def adults(self) -> int:
        return self.passengers

    @property
    def children(self) -> int:
        return len(self.child_ages)

    @field_validator("child_ages")
    @classmethod
    def valid_child_ages(cls, ages: list[int]) -> list[int]:
        if any(not 2 <= age <= 17 for age in ages):
            raise ValueError("Each child must be aged 2 to 17. Children under 2 travel as infants.")
        return ages

    @model_validator(mode="after")
    def validate_route_and_dates(self):
        if self.passengers + self.children > MAX_SEATS:
            raise ValueError(f"A search can include at most {MAX_SEATS} passengers with seats (adults + children).")
        if self.infants > self.passengers:
            raise ValueError("Each infant must travel on an adult's lap: infants cannot outnumber adults.")
        if self.trip_type == "multi-city":
            if not self.legs or not 2 <= len(self.legs) <= MAX_MULTI_CITY_LEGS:
                raise ValueError(f"A multi-city trip needs 2 to {MAX_MULTI_CITY_LEGS} flights.")
            if self.return_date is not None:
                raise ValueError("Return date must be omitted for a multi-city trip.")
            for i, leg in enumerate(self.legs):
                if leg.origin_code == leg.destination_code:
                    raise ValueError(f"Flight {i + 1}: origin and destination must be different.")
                if i and leg.departure_date < self.legs[i - 1].departure_date:
                    raise ValueError(f"Flight {i + 1} cannot depart before flight {i}.")
            first, last = self.legs[0], self.legs[-1]
            if (self.origin_code, self.destination_code, self.departure_date) != (first.origin_code, last.destination_code, first.departure_date):
                raise ValueError("Origin, destination and departure date must match the first and last multi-city flights.")
            return self
        if self.legs:
            raise ValueError("Flights (legs) are only used for multi-city trips.")
        if (
            self.origin.strip().casefold() == self.destination.strip().casefold()
            or self.origin_code == self.destination_code
        ):
            raise ValueError("Origin and destination must be different.")
        if self.return_date and self.return_date < self.departure_date:
            raise ValueError("Return date cannot be before departure date.")
        if self.trip_type == "round-trip" and self.return_date is None:
            raise ValueError("Return date is required for a round trip.")
        if self.trip_type == "one-way" and self.return_date is not None:
            raise ValueError("Return date must be omitted for a one-way trip.")
        return self


class Amenity(BaseModel):
    """Tri-state: available True/False as supplied, None when the provider did not say."""

    available: bool | None = None
    cost: str | None = None  # e.g. "free", "paid"


class SeatInfo(BaseModel):
    type: str | None = None
    pitch: str | None = None
    legroom: str | None = None


class CabinAmenities(BaseModel):
    wifi: Amenity | None = None
    power: Amenity | None = None
    seat: SeatInfo | None = None


class FlightSegment(BaseModel):
    id: str | None = None
    airline: str | None = None
    airline_code: str | None = None
    operating_airline: str | None = None
    marketing_airline: str | None = None
    flight_number: str | None = None
    origin: str
    destination: str
    origin_terminal: str | None = None
    destination_terminal: str | None = None
    departing_at: datetime
    arriving_at: datetime
    duration_minutes: int | None = None
    aircraft: str | None = None
    aircraft_code: str | None = None
    cabin: str | None = None
    cabin_marketing_name: str | None = None
    amenities: CabinAmenities | None = None
    technical_stops: list[str] = Field(default_factory=list)


class FlightItinerary(BaseModel):
    origin: str
    destination: str
    departing_at: datetime
    arriving_at: datetime
    duration_minutes: int | None = None
    stops: int = 0
    segments: list[FlightSegment] = Field(default_factory=list)
    fare_brand_name: str | None = None
    # Slice-level perks as supplied by the provider; None when not supplied.
    priority_check_in: bool | None = None
    priority_boarding: bool | None = None
    advance_seat_selection: bool | None = None


class BaggageAllowance(BaseModel):
    passenger_id: str | None = None
    passenger_type: str | None = None
    baggage_type: str
    quantity: int | None = None
    weight: float | None = None
    weight_unit: str | None = None
    slice_index: int | None = None  # which itinerary (0 = outbound) the allowance applies to


class FareCondition(BaseModel):
    allowed: bool | None = None
    penalty_amount: float | None = None
    penalty_currency: str | None = None


class FareConditions(BaseModel):
    """Offer-level conditions exactly as supplied by the provider; None when not supplied."""

    refund_before_departure: FareCondition | None = None
    change_before_departure: FareCondition | None = None


class FlightOffer(BaseModel):
    id: str
    provider: str
    data_status: Literal["demo", "test", "live"] = "demo"
    retrieved_at: datetime
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_date: date
    departure_time: str
    arrival_time: str
    duration_minutes: int
    stops: int
    price: float
    currency: str = "USD"
    baggage_kg: int | None = None  # Legacy field retained for existing frontend compatibility.
    cabin: str
    refundable: bool | None = None
    disclaimer: str = "Simulated demo offer. Not a live fare or current availability."
    itineraries: list[FlightItinerary] = Field(default_factory=list)
    baggage_allowances: list[BaggageAllowance] = Field(default_factory=list)
    conditions: FareConditions | None = None
    airline_code: str | None = None
    airline_logo_url: str | None = None
    conditions_of_carriage_url: str | None = None
    # Price breakdown exactly as supplied; None when the provider gives only a total.
    base_amount: float | None = None
    base_currency: str | None = None
    tax_amount: float | None = None
    tax_currency: str | None = None
    expires_at: datetime | None = None
    total_emissions_kg: float | None = None
    passenger_count: int | None = None
    # Whether the provider can return seat maps / paid extras for this offer (fetched on demand).
    supports_seat_maps: bool = False
    supports_extra_services: bool = False


class FlightSearchResponse(BaseModel):
    data_status: Literal["demo", "test", "live"] = "demo"
    source_message: str
    results: list[FlightOffer]
    search_id: int | None = None
    provider: str | None = None
