"""Recent real fares from the Aviasales Data API (Travelpayouts).

The Data API returns the cheapest fares that Aviasales users found for a route and
dates during the last few days. They are real market prices, but cached: seats and
the exact price must be confirmed on the booking site. Offers are therefore marked
``data_status="recent"`` and carry a booking link to Aviasales (with the partner
marker) instead of claiming live availability.

Limits of the source, reported to the user rather than worked around:
- economy fares only, one adult per fare (totals for more travellers are estimates);
- no multi-city;
- no per-segment detail (flight number of the first flight, total time and stops only).
"""

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.core.config import Settings
from app.providers.errors import FlightProviderError
from app.schemas.flight import FlightItinerary, FlightOffer, FlightSearchRequest
from app.services.airport_service import get_airport

logger = logging.getLogger(__name__)

AIRLINES_URL = "https://api.travelpayouts.com/data/en/airlines.json"
LOGO_URL = "https://pics.avs.io/120/120/{code}.png"
BOOKING_HOST = "https://www.aviasales.com"
CACHE_SECONDS = 15 * 60  # Travelpayouts asks partners to cache Data API answers
MAX_TRIP_DAYS = 30  # the Data API answers HTTP 400 when the return is later than this
PAIR_EACH_WAY = 6  # longer trips: the cheapest one-way fares each way that are paired up

_airline_names: dict[str, str] | None = None
_cache: dict[tuple, tuple[float, list[dict]]] = {}
_lock = threading.Lock()


class TravelpayoutsError(FlightProviderError):
    pass


def _local(moment: datetime, airport_code: str) -> datetime:
    """Express an instant in the airport's own timezone (arrival times are local)."""
    airport = get_airport(airport_code)
    try:
        return moment.astimezone(ZoneInfo(airport.tz)) if airport and airport.tz else moment
    except ZoneInfoNotFoundError:
        return moment


def _too_long(request: FlightSearchRequest) -> bool:
    return (request.trip_type == "round-trip" and request.return_date is not None
            and (request.return_date - request.departure_date).days > MAX_TRIP_DAYS)


class TravelpayoutsFlightProvider:
    name = "Aviasales (Travelpayouts)"
    data_status = "recent"

    def __init__(self, settings: Settings):
        token = (settings.travelpayouts_token or "").strip()
        if not token:
            raise TravelpayoutsError("FLIGHT_PROVIDER is travelpayouts but TRAVELPAYOUTS_TOKEN is not configured.")
        self.token = token
        self.marker = (settings.travelpayouts_marker or "").strip()
        self.base_url = settings.travelpayouts_api_url.rstrip("/")
        self.timeout = settings.travelpayouts_timeout_seconds

    # ------------------------------------------------------------------ http
    def _get(self, url: str, params: dict | None = None) -> Any:
        try:
            with httpx.Client(timeout=self.timeout, headers={"X-Access-Token": self.token, "Accept-Encoding": "gzip"}) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise TravelpayoutsError("The fare source did not respond in time. Please try again.") from exc
        except httpx.HTTPError as exc:
            raise TravelpayoutsError("Could not reach the fare source. Check your internet connection.") from exc
        if response.status_code in (401, 403):
            raise TravelpayoutsError("The fare source rejected the API token. Check TRAVELPAYOUTS_TOKEN.")
        if response.status_code == 429:
            raise TravelpayoutsError("The fare source is busy right now. Please try again in a minute.")
        if response.status_code >= 400:
            raise TravelpayoutsError(f"The fare source returned an error (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError as exc:
            raise TravelpayoutsError("The fare source returned an unexpected response.") from exc

    def _airline_name(self, code: str) -> str:
        global _airline_names
        if _airline_names is None:
            try:
                rows = self._get(AIRLINES_URL)
                _airline_names = {r["code"]: r.get("name_translations", {}).get("en") or r.get("name") or r["code"]
                                  for r in rows if isinstance(r, dict) and r.get("code")}
            except TravelpayoutsError:
                logger.warning("Airline names unavailable; showing airline codes.")
                _airline_names = {}
        return _airline_names.get(code) or code

    # ---------------------------------------------------------------- search
    def _fares(self, request: FlightSearchRequest) -> list[dict]:
        round_trip = request.trip_type == "round-trip"
        params = {
            "origin": request.origin_code, "destination": request.destination_code,
            "departure_at": request.departure_date.isoformat(), "one_way": "false" if round_trip else "true",
            "currency": "usd", "sorting": "price", "direct": "false", "limit": 30, "page": 1,
        }
        if round_trip and request.return_date:
            params["return_at"] = request.return_date.isoformat()
        return self._query(params)

    def _query(self, params: dict) -> list[dict]:
        key = tuple(sorted(params.items()))
        now = time.time()
        with _lock:
            hit = _cache.get(key)
            if hit and now - hit[0] < CACHE_SECONDS:
                return hit[1]
        body = self._get(f"{self.base_url}/aviasales/v3/prices_for_dates", params)
        if not isinstance(body, dict) or body.get("success") is False:
            raise TravelpayoutsError(f"The fare source could not answer this search{': ' + str(body.get('error')) if isinstance(body, dict) and body.get('error') else ''}.")
        fares = [f for f in body.get("data") or [] if isinstance(f, dict)]
        with _lock:
            _cache[key] = (now, fares)
        return fares

    def search(self, request: FlightSearchRequest) -> list[FlightOffer]:
        if request.trip_type == "multi-city":
            raise TravelpayoutsError("Multi-city trips aren't available from the current fare source. Search each flight separately.")
        if request.cabin != "Economy":
            raise TravelpayoutsError("The current fare source has economy fares only. Choose Economy to see prices.")
        travellers = request.adults + request.children
        retrieved = datetime.now(timezone.utc)
        if _too_long(request):
            return self._two_one_ways(request, travellers, retrieved)
        offers = self._round_trip_or_one_way(request, travellers, retrieved)
        # No round-trip fare on these dates: two one-way tickets may still exist.
        if not offers and request.trip_type == "round-trip" and request.return_date:
            return self._two_one_ways(request, travellers, retrieved)
        return offers

    def _round_trip_or_one_way(self, request: FlightSearchRequest, travellers: int, retrieved: datetime) -> list[FlightOffer]:
        # The same itinerary is often reported by several agencies or fare types: keep the cheapest.
        best: dict[tuple, FlightOffer] = {}
        for fare in self._fares(request):
            offer = self._map(fare, request, travellers, retrieved)
            if offer is None:
                continue
            key = (offer.flight_number, *(i.departing_at for i in offer.itineraries), *(i.arriving_at for i in offer.itineraries))
            if key not in best or offer.price < best[key].price:
                best[key] = offer
        return sorted(best.values(), key=lambda o: o.price)

    def _two_one_ways(self, request: FlightSearchRequest, travellers: int, retrieved: datetime) -> list[FlightOffer]:
        """A round trip priced as two real one-way fares.

        Used when the source has no round-trip fare for the dates, or cannot price the
        trip at all (longer than 30 days). The cheapest outbound and return fares are
        paired; each keeps its own booking link, and the offer says plainly that these
        are two separate tickets.
        """
        outbound = request.model_copy(update={"trip_type": "one-way", "return_date": None})
        inbound = request.model_copy(update={"trip_type": "one-way", "return_date": None, "origin": request.destination,
                                             "destination": request.origin, "departure_date": request.return_date})
        outs = self._round_trip_or_one_way(outbound, travellers, retrieved)[:PAIR_EACH_WAY]
        backs = self._round_trip_or_one_way(inbound, travellers, retrieved)[:PAIR_EACH_WAY] if outs else []
        why = (f"the fare source only prices round trips of up to {MAX_TRIP_DAYS} days" if _too_long(request)
               else "no round-trip fare was found for these dates")
        pairs = []
        for out in outs:
            for back in backs:
                if back.itineraries[0].departing_at <= out.itineraries[0].arriving_at:
                    continue
                sellers = " + ".join(dict.fromkeys(s for s in (out.sold_by, back.sold_by) if s)) or None
                pairs.append(out.model_copy(update={
                    "id": "tp2_" + hashlib.sha256(f"{out.id}|{back.id}".encode()).hexdigest()[:24],
                    "itineraries": [*out.itineraries, *back.itineraries],
                    "price": round(out.price + back.price, 2),
                    "airline": out.airline if out.airline == back.airline else f"{out.airline} + {back.airline}",
                    "return_booking_url": back.booking_url,
                    "sold_by": sellers,
                    "disclaimer": (
                        f"Two separate one-way tickets ({why}). "
                        "Book the outbound and return flights separately; if one is delayed or cancelled, the other airline "
                        "is not obliged to rebook you. " + out.disclaimer
                    ),
                }))
        return sorted(pairs, key=lambda o: o.price)

    @staticmethod
    def _month_params(origin: str, destination: str, day) -> dict:
        return {"origin": origin, "destination": destination, "departure_at": day.strftime("%Y-%m"), "one_way": "true",
                "currency": "usd", "sorting": "price", "direct": "false", "limit": 100, "page": 1}

    def _cheapest_by_day(self, origin: str, destination: str, day) -> dict:
        """Cheapest one-way fare for each future day of ``day``'s month."""
        today = datetime.now(timezone.utc).date()
        cheapest: dict = {}
        for fare in self._query(self._month_params(origin, destination, day)):
            try:
                when = datetime.fromisoformat(fare["departure_at"]).date()
                price = float(fare["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if when >= today and (when not in cheapest or price < cheapest[when]):
                cheapest[when] = price
        return cheapest

    def nearby_dates(self, request: FlightSearchRequest, limit: int = 6) -> list[dict]:
        """Closest dates that do have recent fares, for when the exact dates have none.

        The source only holds fares that users recently found, so an exact pair of dates
        is often empty while the days around it are not. Querying the whole month(s)
        returns those real fares; the cheapest per date pair is offered, nearest first.
        Round trips also count days with a one-way fare each way, which the search pairs.
        """
        if request.trip_type == "multi-city" or request.cabin != "Economy":
            return []
        round_trip = request.trip_type == "round-trip" and request.return_date is not None
        cheapest: dict[tuple, float] = {}

        def offer(pair: tuple, price: float) -> None:
            if pair not in cheapest or price < cheapest[pair]:
                cheapest[pair] = price

        if not round_trip:
            for day, price in self._cheapest_by_day(request.origin_code, request.destination_code, request.departure_date).items():
                offer((day, None), price)
        else:
            if not _too_long(request):
                params = {**self._month_params(request.origin_code, request.destination_code, request.departure_date),
                          "one_way": "false", "return_at": request.return_date.strftime("%Y-%m")}
                for fare in self._query(params):
                    try:
                        out = datetime.fromisoformat(fare["departure_at"]).date()
                        back = datetime.fromisoformat(fare["return_at"]).date()
                        price = float(fare["price"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if out >= datetime.now(timezone.utc).date() and back >= out:
                        offer((out, back), price)
            # Days that have a one-way fare each way also work: the search pairs two one-way tickets.
            outs = self._cheapest_by_day(request.origin_code, request.destination_code, request.departure_date)
            backs = self._cheapest_by_day(request.destination_code, request.origin_code, request.return_date)
            near_outs = sorted(outs, key=lambda d: abs((d - request.departure_date).days))[:3]
            near_backs = sorted(backs, key=lambda d: abs((d - request.return_date).days))[:3]
            for out in near_outs:
                for back in near_backs:
                    if back > out:
                        offer((out, back), outs[out] + backs[back])

        def distance(pair: tuple) -> int:
            out, back = pair
            return abs((out - request.departure_date).days) + (abs((back - request.return_date).days) if back else 0)

        pairs = sorted(cheapest, key=lambda p: (distance(p), cheapest[p]))[:limit]
        return [{"departure_date": out.isoformat(), "return_date": back.isoformat() if back else None,
                 "price": round(cheapest[(out, back)], 2), "currency": "USD"} for out, back in pairs]

    def _map(self, fare: dict, request: FlightSearchRequest, travellers: int, retrieved: datetime) -> FlightOffer | None:
        try:
            departing = datetime.fromisoformat(fare["departure_at"])
            price = float(fare["price"])
        except (KeyError, TypeError, ValueError):
            return None
        origin = fare.get("origin_airport") or request.origin_code
        destination = fare.get("destination_airport") or request.destination_code
        code = (fare.get("airline") or "").upper()
        out_minutes = int(fare.get("duration_to") or fare.get("duration") or 0)
        arriving = _local(departing + timedelta(minutes=out_minutes), destination)
        itineraries = [FlightItinerary(origin=origin, destination=destination, departing_at=departing, arriving_at=arriving,
                                       duration_minutes=out_minutes or None, stops=int(fare.get("transfers") or 0))]
        if fare.get("return_at"):
            try:
                back_departing = datetime.fromisoformat(fare["return_at"])
                back_minutes = int(fare.get("duration_back") or 0)
                itineraries.append(FlightItinerary(
                    origin=destination, destination=origin, departing_at=back_departing,
                    arriving_at=_local(back_departing + timedelta(minutes=back_minutes), origin),
                    duration_minutes=back_minutes or None, stops=int(fare.get("return_transfers") or 0)))
            except (TypeError, ValueError):
                pass
        # Only a path on the booking site is accepted: "//evil.example" or "@evil.example" would
        # otherwise turn the link into a redirect to another host.
        link = fare.get("link") or ""
        safe_link = link.startswith("/") and not link.startswith("//") and "\\" not in link and "@" not in link.split("?", 1)[0]
        booking_url = (f"{BOOKING_HOST}{link}" + (f"&marker={self.marker}" if self.marker else "")) if safe_link else None
        estimated = travellers > 1
        return FlightOffer(
            id="tp_" + hashlib.sha256(f"{link}|{price}|{fare.get('departure_at')}".encode()).hexdigest()[:24],
            provider=self.name,
            data_status="recent",
            retrieved_at=retrieved,
            airline=self._airline_name(code) if code else "Airline not supplied",
            airline_code=code or None,
            airline_logo_url=LOGO_URL.format(code=code) if code else None,
            flight_number=f"{code} {fare['flight_number']}".strip() if fare.get("flight_number") else code,
            origin=origin,
            destination=destination,
            departure_date=departing.date(),
            departure_time=departing.strftime("%H:%M"),
            arrival_time=arriving.strftime("%H:%M"),
            duration_minutes=out_minutes,
            stops=int(fare.get("transfers") or 0),
            price=round(price * travellers, 2),
            currency="USD",
            cabin="Economy",
            passenger_count=travellers,
            itineraries=itineraries,
            booking_url=booking_url,
            sold_by=fare.get("gate"),
            price_is_estimate=estimated,
            disclaimer=(
                "Recent fare found by Aviasales users in the last few days, not a live quote: check the final price "
                "and availability on the booking site."
                + (f" Total estimated as one adult's fare × {travellers} travellers; children are often cheaper." if estimated else "")
            ),
        )
