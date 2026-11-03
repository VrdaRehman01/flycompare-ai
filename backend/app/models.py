
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FlightSearchHistory(Base):
    """Store a record of each flight search."""

    __tablename__ = "flight_search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    origin: Mapped[str] = mapped_column(String(100), nullable=False)
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trip_type: Mapped[str] = mapped_column(String(20), nullable=False)
    passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    cabin: Mapped[str] = mapped_column(String(30), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Added by migration 0001. Nullable so records created before accounts existed stay valid.
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    origin_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    destination_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Added by migration 0002.
    children: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    infants: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    legs: Mapped[list | None] = mapped_column(JSON, nullable=True)  # multi-city itinerary


class FareObservation(Base):
    """One offer price seen in one search. Basis for genuine price history."""

    __tablename__ = "fare_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    data_status: Mapped[str] = mapped_column(String(10), nullable=False)
    origin_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    destination_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trip_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cabin: Mapped[str] = mapped_column(String(30), nullable=False)
    passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    airline: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    stops: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Added by migration 0002: connection airports of the outbound journey, e.g. "DOH,IST".
    connections: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Added by migration 0004: airline identity as supplied by the provider (for logos on deals).
    airline_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    airline_logo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    # Added by migration 0005. Set once the user proves they receive mail at ``email``.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailCode(Base):
    """A one-time sign-in or verification code sent by email. Only an HMAC of the code is stored.

    ``purpose`` is "login" (sign in, creating the account if needed) or "register"
    (``payload`` holds the pending name and password hash; the account is created
    only once the code proves the address belongs to the registrant).
    """

    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SavedFlight(Base):
    """A saved comparison snapshot. Not a booking or a price guarantee."""

    __tablename__ = "saved_flights"
    __table_args__ = (UniqueConstraint("user_id", "offer_id", name="uq_saved_flight_user_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    offer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    offer: Mapped[dict] = mapped_column(JSON, nullable=False)
    search: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RecentlyViewedFlight(Base):
    __tablename__ = "recently_viewed_flights"
    __table_args__ = (UniqueConstraint("user_id", "offer_id", name="uq_recent_flight_user_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    offer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    offer: Mapped[dict] = mapped_column(JSON, nullable=False)
    search: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FavouriteDestination(Base):
    __tablename__ = "favourite_destinations"
    __table_args__ = (UniqueConstraint("user_id", "airport_code", name="uq_favourite_user_airport"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    airport_code: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SavedRoute(Base):
    """A route a signed-in user wants to keep an eye on (no dates: a route, not a trip)."""

    __tablename__ = "saved_routes"
    __table_args__ = (UniqueConstraint("user_id", "origin_code", "destination_code", name="uq_saved_route_user_route"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    origin_code: Mapped[str] = mapped_column(String(3), nullable=False)
    destination_code: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PriceAlert(Base):
    """A signed-in user's request to be emailed when a trip's fare drops to a target price.

    The checker re-searches the trip periodically and stores what it saw, so the user
    can see when it was last checked and the lowest fare found, not just the outcome.
    """

    __tablename__ = "price_alerts"
    __table_args__ = (UniqueConstraint("user_id", "origin_code", "destination_code", "departure_date", "return_date", name="uq_alert_user_trip"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    origin_code: Mapped[str] = mapped_column(String(3), nullable=False)
    destination_code: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_price: Mapped[float | None] = mapped_column(Float, nullable=True)


class DestinationImage(Base):
    """Cached destination photo lookup (Wikipedia / Wikimedia Commons) including attribution.

    ``status`` is "ok" (photo found) or "none" (no suitable free photo); ``fetched_at``
    is the retrieval time and drives cache expiry.
    """

    __tablename__ = "destination_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    url_2x: Mapped[str | None] = mapped_column(String(600), nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    licence: Mapped[str | None] = mapped_column(String(120), nullable=True)
    artist: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
