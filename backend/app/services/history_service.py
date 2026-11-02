from collections.abc import Iterable

from app.models import FlightSearchHistory


def history_rows(rows: Iterable[FlightSearchHistory]) -> list[dict]:
    """Serialise search history, keeping the original fields for existing clients."""
    return [
        {
            "id": s.id,
            "origin": s.origin,
            "destination": s.destination,
            "origin_code": s.origin_code,
            "destination_code": s.destination_code,
            "departure_date": s.departure_date,
            "return_date": s.return_date,
            "trip_type": s.trip_type,
            "passengers": s.passengers,
            "children": s.children or 0,
            "infants": s.infants or 0,
            "legs": s.legs,
            "cabin": s.cabin,
            "result_count": s.result_count,
            "data_status": s.data_status,
            "currency": s.currency,
            "min_price": s.min_price,
            "created_at": s.created_at,
        }
        for s in rows
    ]
