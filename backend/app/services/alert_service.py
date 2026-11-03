"""Price alerts: email a user when a trip's fare drops to their target.

Checking: each active alert is re-searched at most every ``alert_recheck_hours`` with
the configured flight provider (one adult, economy). The cheapest fare in the alert's
currency is stored with the check time. An email goes out when that fare is at or
below the target and lower than any fare already reported, so a user hears about each
new low once rather than on every check. Alerts for past departure dates are switched
off. Provider or email failures are recorded on the alert and retried next round;
they never produce a notification.
"""

import html
import logging
import threading
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import PriceAlert, User
from app.providers.errors import FlightProviderError
from app.providers.factory import ProviderConfigError, build_flight_provider
from app.schemas.flight import FlightSearchRequest
from app.services import email_service
from app.services.airport_service import get_airport

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def alert_out(a: PriceAlert) -> dict:
    return {
        "id": a.id, "origin": a.origin_code, "destination": a.destination_code,
        "departure_date": a.departure_date, "return_date": a.return_date,
        "target_price": a.target_price, "currency": a.currency, "active": a.active,
        "created_at": a.created_at, "last_checked_at": a.last_checked_at, "last_price": a.last_price,
        "last_error": a.last_error, "notified_at": a.notified_at, "notified_price": a.notified_price,
    }


def list_alerts(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(PriceAlert).where(PriceAlert.user_id == user.id).order_by(PriceAlert.active.desc(), PriceAlert.departure_date)).all()
    return [alert_out(a) for a in rows]


def create_alert(db: Session, user: User, origin: str, destination: str, departure: date, return_date: date | None,
                 target_price: float, currency: str) -> dict:
    settings = get_settings()
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email first: sign out and sign in with an emailed code.")
    if get_airport(origin) is None or get_airport(destination) is None:
        raise HTTPException(status_code=422, detail="Choose airports from the list.")
    if departure < date.today():
        raise HTTPException(status_code=422, detail="The departure date has passed.")
    active = db.scalars(select(PriceAlert).where(PriceAlert.user_id == user.id, PriceAlert.active.is_(True))).all()
    existing = next((a for a in active if (a.origin_code, a.destination_code, a.departure_date, a.return_date) == (origin, destination, departure, return_date)), None)
    if existing:
        existing.target_price, existing.currency = target_price, currency
        existing.notified_price = None  # a new target deserves a fresh notification
        db.commit()
        return alert_out(existing)
    if len(active) >= settings.alerts_per_user:
        raise HTTPException(status_code=409, detail=f"You can have up to {settings.alerts_per_user} active alerts. Remove one first.")
    # A finished alert for the same trip is reused (the trip is unique per user).
    alert = db.scalar(select(PriceAlert).where(PriceAlert.user_id == user.id, PriceAlert.origin_code == origin, PriceAlert.destination_code == destination,
                                               PriceAlert.departure_date == departure, PriceAlert.return_date.is_(return_date) if return_date is None else PriceAlert.return_date == return_date))
    if alert is None:
        alert = PriceAlert(user_id=user.id, origin_code=origin, destination_code=destination, departure_date=departure, return_date=return_date)
        db.add(alert)
    alert.target_price, alert.currency, alert.active = target_price, currency, True
    alert.last_checked_at = alert.last_price = alert.last_error = alert.notified_at = alert.notified_price = None
    db.commit()
    db.refresh(alert)
    return alert_out(alert)


def delete_alert(db: Session, user: User, alert_id: int) -> None:
    alert = db.get(PriceAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert not found.")
    db.delete(alert)
    db.commit()


# ------------------------------------------------------------------ checking

def _email(user: User, alert: PriceAlert, price: float, booking_url: str | None) -> None:
    settings = get_settings()
    # Provider data is untrusted: only an http(s) link goes into the email, escaped for HTML.
    if booking_url and not booking_url.startswith(("https://", "http://")):
        booking_url = None
    booking_href = html.escape(booking_url, quote=True) if booking_url else None
    trip = f"{alert.origin_code} → {alert.destination_code}"
    dates = alert.departure_date.strftime("%d %b %Y") + (f" – {alert.return_date.strftime('%d %b %Y')}" if alert.return_date else " (one way)")
    manage = settings.app_public_url.rstrip("/") + "/#/account/alerts"
    amount, target = f"{alert.currency} {price:,.0f}", f"{alert.currency} {alert.target_price:,.0f}"
    subject = f"Price alert: {trip} is now {amount}"
    text = (f"Good news: the lowest fare we found for {trip}, {dates}, is {amount}, at or below your target of {target}.\n\n"
            + (f"Check the price and book: {booking_url}\n\n" if booking_url else "")
            + "Fares change quickly and this one may not last. It is a recent fare, so confirm the final price on the booking site.\n\n"
            f"Manage your alerts: {manage}")
    body_html = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;color:#172844\">"
        "<h2 style=\"margin:0 0 12px;font-size:20px\">FlyCompare <span style=\"color:#1a6dff\">AI</span></h2>"
        f"<p style=\"font-size:15px\">The lowest fare for <b>{trip}</b>, {dates}, dropped to</p>"
        f"<p style=\"font-size:30px;font-weight:700;margin:8px 0\">{amount}</p>"
        f"<p style=\"font-size:14px;color:#64748b;margin-top:0\">Your target: {target}</p>"
        + (f"<p><a href=\"{booking_href}\" style=\"display:inline-block;background:#1a6dff;color:#fff;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:700\">Check price &amp; book</a></p>" if booking_url else "")
        + "<p style=\"font-size:13px;color:#64748b\">Fares change quickly. This is a recent fare: confirm the final price on the booking site.</p>"
        f"<p style=\"font-size:13px\"><a href=\"{html.escape(manage, quote=True)}\">Manage your alerts</a></p></div>"
    )
    email_service.send(user.email, subject, text, body_html)


def check_alert(db: Session, alert: PriceAlert, provider) -> str:
    """Re-search one alert. Returns "notified", "checked", "expired" or "error"."""
    now = _now()
    if alert.departure_date < date.today():
        alert.active = False
        db.commit()
        return "expired"
    request = FlightSearchRequest(
        origin=alert.origin_code, destination=alert.destination_code, departure_date=alert.departure_date,
        return_date=alert.return_date, trip_type="round-trip" if alert.return_date else "one-way", passengers=1, cabin="Economy",
    )
    alert.last_checked_at = now
    try:
        offers = [o for o in provider.search(request) if o.currency == alert.currency]
    except FlightProviderError as exc:
        alert.last_error = str(exc)[:200]
        db.commit()
        return "error"
    alert.last_error = None
    if not offers:
        alert.last_price = None
        db.commit()
        return "checked"
    best = min(offers, key=lambda o: o.price)
    alert.last_price = best.price
    is_new_low = alert.notified_price is None or best.price < alert.notified_price
    if best.price <= alert.target_price and is_new_low:
        user = db.get(User, alert.user_id)
        try:
            _email(user, alert, best.price, best.booking_url)
        except (email_service.EmailNotConfigured, email_service.EmailDeliveryFailed) as exc:
            alert.last_error = "Price reached your target, but the email could not be sent; retrying next check."
            logger.warning("Alert email failed: %s", exc.__class__.__name__)
            db.commit()
            return "error"
        alert.notified_at, alert.notified_price = now, best.price
        db.commit()
        return "notified"
    db.commit()
    return "checked"


def run_due(db: Session, limit: int = 50) -> dict:
    """Check every active alert not checked within the recheck window."""
    settings = get_settings()
    counts = {"notified": 0, "checked": 0, "expired": 0, "error": 0}
    try:
        provider, _ = build_flight_provider(settings)
    except ProviderConfigError as exc:
        logger.warning("Price alerts skipped: %s", exc)
        return {**counts, "skipped": str(exc)}
    cutoff = _now() - timedelta(hours=settings.alert_recheck_hours)
    due = db.scalars(
        select(PriceAlert).where(PriceAlert.active.is_(True), or_(PriceAlert.last_checked_at.is_(None), PriceAlert.last_checked_at < cutoff))
        .order_by(PriceAlert.last_checked_at.is_not(None), PriceAlert.last_checked_at).limit(limit)
    ).all()
    for alert in due:
        counts[check_alert(db, alert, provider)] += 1
    return counts


class AlertScheduler:
    """Background thread that runs ``run_due`` every few minutes inside the API process."""

    def __init__(self, session_factory, interval_minutes: int):
        self._factory = session_factory
        self._interval = interval_minutes * 60
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="price-alerts", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                with self._factory() as db:
                    counts = run_due(db)
                if any(counts.get(k) for k in ("notified", "checked", "expired", "error")):
                    logger.info("Price alerts checked: %s", counts)
            except Exception:  # noqa: BLE001 - the loop must survive any single failure
                logger.exception("Price alert check failed")
