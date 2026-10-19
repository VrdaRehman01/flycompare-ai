
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import FlightSearchHistory


def test_flight_search_history_can_be_saved_and_retrieved():
    # Use a temporary in-memory database so the test
    # does not modify the real flycompare.db file.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)

    try:
        with TestSession() as session:
            search = FlightSearchHistory(
                origin="KHI",
                destination="JFK",
                departure_date=date(2026, 11, 15),
                return_date=date(2026, 11, 25),
                trip_type="round-trip",
                passengers=1,
                cabin="Economy",
                result_count=3,
            )

            session.add(search)
            session.commit()
            search_id = search.id

        with TestSession() as session:
            saved_search = session.scalar(
                select(FlightSearchHistory).where(
                    FlightSearchHistory.id == search_id
                )
            )

            assert saved_search is not None
            assert saved_search.origin == "KHI"
            assert saved_search.destination == "JFK"
            assert saved_search.result_count == 3

    finally:
        test_engine.dispose()
