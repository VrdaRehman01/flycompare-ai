from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class FlightSearchRequest(BaseModel):
    origin: str = Field(min_length=3, max_length=100)
    destination: str = Field(min_length=3, max_length=100)
    departure_date: date
    return_date: date | None = None
    trip_type: Literal["round-trip", "one-way"] = "round-trip"
    passengers: int = Field(default=1, ge=1, le=9)
    cabin: Literal["Economy", "Premium economy", "Business", "First class"] = "Economy"

    @model_validator(mode="after")
    def validate_route_and_dates(self):
        if self.origin.strip().casefold() == self.destination.strip().casefold():
            raise ValueError("Origin and destination must be different.")
        if self.return_date and self.return_date < self.departure_date:
            raise ValueError("Return date cannot be before departure date.")
        if self.trip_type == "round-trip" and self.return_date is None:
            raise ValueError("Return date is required for a round trip.")
        return self


class FlightOffer(BaseModel):
    id: str
    provider: str
    data_status: Literal["demo"] = "demo"
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
    baggage_kg: int | None = None
    cabin: str
    refundable: bool | None = None
    disclaimer: str = "Simulated demo offer. Not a live fare or current availability."


class FlightSearchResponse(BaseModel):
    data_status: Literal["demo"] = "demo"
    source_message: str
    results: list[FlightOffer]
