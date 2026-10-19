from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.models import FlightSearchHistory
from app.providers.mock_provider import MockDemoFlightProvider
from app.schemas.flight import FlightSearchRequest, FlightSearchResponse

router = APIRouter(prefix="/api/flights", tags=["flights"])
provider = MockDemoFlightProvider()


@router.post(
    "/search",
    response_model=FlightSearchResponse,
    summary="Search demo flight offers",
)
def search_flights(
    request: FlightSearchRequest,
    db: Session = Depends(get_db),
) -> FlightSearchResponse:
    """Return simulated offers and record the successful search."""
    results = provider.search(request)

    history = FlightSearchHistory(
        origin=request.origin,
        destination=request.destination,
        departure_date=request.departure_date,
        return_date=request.return_date,
        trip_type=request.trip_type,
        passengers=request.passengers,
        cabin=request.cabin,
        result_count=len(results),
    )

    try:
        db.add(history)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return FlightSearchResponse(
        source_message=(
            "Demo results generated for development only. These are simulated offers, "
            "not live prices, seat availability, or bookable tickets."
        ),
        results=results,
    )

@router.get("/history", summary="Get recent flight search history")
def get_search_history(
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return the 50 most recent saved searches."""
    searches = db.scalars(
        select(FlightSearchHistory)
        .order_by(FlightSearchHistory.created_at.desc())
        .limit(50)
    ).all()

    return [
        {
            "id": search.id,
            "origin": search.origin,
            "destination": search.destination,
            "departure_date": search.departure_date,
            "return_date": search.return_date,
            "trip_type": search.trip_type,
            "passengers": search.passengers,
            "cabin": search.cabin,
            "result_count": search.result_count,
            "created_at": search.created_at,
        }
        for search in searches
    ]


@router.get("/analytics", summary="Get flight search analytics")
def get_search_analytics(
    db: Session = Depends(get_db),
) -> dict:
    """Summarize saved flight searches."""
    searches = db.scalars(
        select(FlightSearchHistory).order_by(
            FlightSearchHistory.created_at.desc()
        )
    ).all()

    destination_counts: dict[str, int] = {}
    for search in searches:
        destination = search.destination.strip()
        destination_counts[destination] = (
            destination_counts.get(destination, 0) + 1
        )

    most_searched_destination = (
        max(destination_counts, key=destination_counts.get)
        if destination_counts
        else None
    )

    return {
        "total_searches": len(searches),
        "unique_destinations": len(destination_counts),
        "most_searched_destination": most_searched_destination,
        "destination_counts": destination_counts,
        "latest_search": (
            {
                "origin": searches[0].origin,
                "destination": searches[0].destination,
                "created_at": searches[0].created_at,
            }
            if searches
            else None
        ),
    }
