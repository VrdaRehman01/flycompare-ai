import logging

from sqlalchemy.orm import Session

from app.models import FareObservation, FlightSearchHistory, User
from app.schemas.flight import FlightOffer, FlightSearchRequest, FlightSearchResponse

logger = logging.getLogger(__name__)

SOURCE_MESSAGES = {
    "test": "Duffel test-environment results. These are sandbox offers, not live prices or bookable tickets.",
    "live": "Live Duffel search results. Prices and availability may change and should be revalidated before booking.",
    "demo": "Demo results generated for development only. These are simulated offers, not live prices, seat availability, or bookable tickets.",
    "recent": "Recent fares found by Aviasales users in the last few days. They are real prices but not live quotes: confirm the price and seats on the booking site.",
}


def _lowest(results: list[FlightOffer]) -> tuple[str | None, float | None]:
    """Lowest fare and its currency. Mixed-currency result sets report no single minimum."""
    currencies = {r.currency for r in results}
    if len(currencies) != 1:
        return None, None
    return currencies.pop(), min(r.price for r in results)


def _connections(offer: FlightOffer) -> str | None:
    """Connection airports of the outbound journey, e.g. "DOH" or "DOH,IST"."""
    if not offer.itineraries:
        return None
    via = [segment.destination for segment in offer.itineraries[0].segments[:-1] if segment.destination]
    return ",".join(via)[:40] or None


def record_search(
    db: Session,
    request: FlightSearchRequest,
    results: list[FlightOffer],
    provider_name: str,
    data_status: str,
    user: User | None,
) -> FlightSearchHistory:
    currency, min_price = _lowest(results)
    history = FlightSearchHistory(
        origin=request.origin,
        destination=request.destination,
        origin_code=request.origin_code,
        destination_code=request.destination_code,
        departure_date=request.departure_date,
        return_date=request.return_date,
        trip_type=request.trip_type,
        passengers=request.passengers,
        cabin=request.cabin,
        children=request.children,
        infants=request.infants,
        legs=[
            {"origin": leg.origin_code, "destination": leg.destination_code, "departure_date": leg.departure_date.isoformat()}
            for leg in request.legs
        ] if request.legs else None,
        result_count=len(results),
        user_id=user.id if user else None,
        provider=provider_name,
        data_status=data_status,
        currency=currency,
        min_price=min_price,
    )
    db.add(history)
    db.flush()

    # Store every returned offer price as a genuine observation. Simulated demo
    # offers are never stored, so they can never appear as price history.
    # Multi-city fares, and fares including children or infants, are priced
    # differently from a simple adults-only route, so they are not stored as
    # observations; that keeps every price history like-for-like.
    comparable = request.trip_type != "multi-city" and request.children == 0 and request.infants == 0
    # "recent" fares are real prices reported by the fare source at search time, so they are
    # observations too; they stay labelled and grouped separately from live and test data.
    if data_status in {"test", "live", "recent"} and comparable:
        for offer in results:
            db.add(
                FareObservation(
                    search_id=history.id,
                    provider=provider_name,
                    data_status=data_status,
                    origin_code=request.origin_code,
                    destination_code=request.destination_code,
                    departure_date=request.departure_date,
                    return_date=request.return_date,
                    trip_type=request.trip_type,
                    cabin=request.cabin,
                    passengers=request.passengers,
                    offer_id=offer.id[:100],
                    airline=offer.airline[:120],
                    price=offer.price,
                    currency=offer.currency[:3].upper(),
                    stops=offer.stops,
                    duration_minutes=offer.duration_minutes or None,
                    connections=_connections(offer),
                    airline_code=(offer.airline_code or "")[:3] or None,
                    airline_logo_url=(offer.airline_logo_url or "")[:300] or None,
                )
            )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(history)
    return history


def build_response(results: list[FlightOffer], data_status: str, provider_name: str, search_id: int) -> FlightSearchResponse:
    return FlightSearchResponse(
        data_status=data_status,
        source_message=SOURCE_MESSAGES.get(data_status, SOURCE_MESSAGES["demo"]),
        results=results,
        search_id=search_id,
        provider=provider_name,
    )
