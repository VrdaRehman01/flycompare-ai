from datetime import datetime, timezone
from hashlib import sha256
from app.schemas.flight import FlightOffer, FlightSearchRequest


class MockDemoFlightProvider:
    """Deterministic demo offers for development; never represents live inventory."""

    name = "FlyCompare Demo Provider"

    def search(self, request: FlightSearchRequest) -> list[FlightOffer]:
        route_key = f"{request.origin}|{request.destination}|{request.departure_date}|{request.cabin}"
        seed = int(sha256(route_key.encode()).hexdigest()[:8], 16)
        base = 380 + seed % 520
        now = datetime.now(timezone.utc)
        airlines = [
            ("Example Airways", "EA 214", 0, 635, "08:10", "18:45", 30),
            ("Northstar Air", "NS 802", 1, 820, "10:30", "07:20+1", 20),
            ("Crescent Demo Airlines", "CD 115", 1, 940, "21:15", "16:40+1", 25),
        ]
        offers: list[FlightOffer] = []
        for idx, (airline, number, stops, duration, dep, arr, baggage) in enumerate(airlines):
            price = float(base + idx * 73 + (0 if request.cabin == "Economy" else 160 * (1 + idx)))
            offer_id = sha256(f"{route_key}|{number}".encode()).hexdigest()[:16]
            offers.append(FlightOffer(
                id=offer_id,
                provider=self.name,
                retrieved_at=now,
                airline=airline,
                flight_number=number,
                origin=request.origin,
                destination=request.destination,
                departure_date=request.departure_date,
                departure_time=dep,
                arrival_time=arr,
                duration_minutes=duration + (seed % 55),
                stops=stops,
                price=price,
                baggage_kg=baggage,
                cabin=request.cabin,
                refundable=(idx == 2),
            ))
        return offers
