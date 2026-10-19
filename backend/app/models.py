
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FlightSearchHistory(Base):
    """Store a record of each flight search."""

    __tablename__ = "flight_search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    origin: Mapped[str] = mapped_column(String(100), nullable=False)
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    departure_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    return_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    trip_type: Mapped[str] = mapped_column(String(20), nullable=False)
    passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    cabin: Mapped[str] = mapped_column(String(30), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
