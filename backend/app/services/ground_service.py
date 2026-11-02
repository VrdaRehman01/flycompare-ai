"""Car rental and airport transfers.

No car-rental or transfer provider is connected, so offers are deterministic
demo data built from real inputs: the chosen airport, its distance to the city
centre, rental length, driver age and party size. The rules (young-driver fees,
weekly discounts, vehicle capacity) mirror how rental and transfer suppliers
price, so a real provider can replace ``_car_offers``/``_transfer_offers`` while
the API shape stays the same.
"""

from datetime import date, datetime, time

from app.services.airport_service import Airport, haversine_km
from app.services.destination_service import City
from app.data.travel_content import DEFAULT_AIRPORT_KM
from app.services.travel_common import DEMO_NOTICE, centre, cost_index, seeded

DEMO_SUPPLIERS = ("Demo Drive", "Sample Car Hire", "Example Rentals", "Testline Cars")

# category, example model, seats, large bags, small bags, doors, USD/day at cost index 110
CAR_CLASSES = (
    ("Mini", "Kia Picanto or similar", 4, 1, 1, 5, 24),
    ("Economy", "Toyota Yaris or similar", 5, 1, 2, 5, 29),
    ("Compact", "Volkswagen Golf or similar", 5, 2, 2, 5, 36),
    ("Full-size", "Toyota Camry or similar", 5, 2, 3, 4, 52),
    ("SUV", "Toyota RAV4 or similar", 5, 3, 2, 5, 61),
    ("People carrier", "Kia Carnival or similar", 7, 3, 3, 5, 84),
    ("Premium", "BMW 5 Series or similar", 5, 3, 2, 4, 112),
    ("Luxury", "Mercedes-Benz S-Class or similar", 5, 3, 2, 4, 215),
)
MANUAL_COMMON = {"Europe"}

# kind, vehicle, max passengers, max bags, USD base, USD per km (at cost index 110), per person?
TRANSFER_TYPES = (
    ("shared", "Shared shuttle", 1, 1, 6, 0.18, True),
    ("private", "Private sedan", 3, 3, 14, 0.85, False),
    ("private", "Private SUV", 5, 5, 20, 1.05, False),
    ("private", "Private minivan", 7, 7, 26, 1.25, False),
    ("private", "Business-class sedan", 3, 3, 30, 1.7, False),
    ("private", "Private minibus", 14, 14, 45, 1.9, False),
)


def _scale(city: City, power: float = 0.6) -> float:
    return (cost_index(city) / 110) ** power


def _airport(city: City, code: str | None) -> Airport:
    if code:
        for a in city.airports:
            if a.code == code.upper():
                return a
    return city.primary


def search_cars(city: City, airport_code: str | None, pickup: datetime, dropoff: datetime, driver_age: int) -> dict:
    airport = _airport(city, airport_code)
    hours = (dropoff - pickup).total_seconds() / 3600
    days = max(1, int(-(-hours // 24)))  # rental days are charged in started 24-hour blocks
    discount = 0.82 if days >= 7 else 0.92 if days >= 3 else 1.0
    young = 12 if driver_age < 25 else 0
    senior = 8 if driver_age >= 75 else 0
    rng = seeded("cars", city.key, airport.code, pickup.date(), dropoff.date())
    offers = []
    for category, model, seats, large, small, doors, usd in CAR_CLASSES:
        for supplier in rng.sample(DEMO_SUPPLIERS, 2):
            per_day = usd * _scale(city) * discount * (0.86 + 0.3 * rng.random())
            fees = (young + senior) * days
            in_terminal = rng.random() < 0.6
            unlimited = rng.random() < 0.7
            offers.append({
                "id": f"car-{seeded(city.key, airport.code, category, supplier, pickup).randrange(16**10):010x}",
                "category": category, "model": model, "supplier": supplier,
                "supplier_rating": round(7.2 + 2.4 * rng.random(), 1),
                "seats": seats, "bags_large": large, "bags_small": small, "doors": doors,
                "transmission": "Manual" if city.region in MANUAL_COMMON and category in ("Mini", "Economy", "Compact") and rng.random() < 0.6 else "Automatic",
                "air_conditioning": True,
                "fuel_policy": "Full to full" if rng.random() < 0.8 else "Same to same",
                "mileage": "Unlimited" if unlimited else f"{rng.choice([200, 250, 300])} km per day",
                "pickup": f"{airport.name} ({airport.code}) · {'in terminal' if in_terminal else 'free shuttle bus'}",
                "in_terminal": in_terminal,
                "free_cancellation": rng.random() < 0.75,
                "includes": ["Collision damage waiver", "Theft protection", "Third-party liability"],
                "deposit": round(usd * 8 * _scale(city), -1),
                "price_per_day": round(per_day + (young + senior), 2),
                "driver_fees": round(fees, 2),
                "total_price": round(per_day * days + fees, 2),
                "currency": "USD",
            })
    notes = [f"Charged as {days} rental day{'s' if days != 1 else ''} (each started 24 hours counts)."]
    if young:
        notes.append(f"Drivers under 25 pay a young-driver fee (USD {young}/day here).")
    if senior:
        notes.append(f"Drivers 75 and over pay a senior-driver fee (USD {senior}/day here).")
    if discount < 1:
        notes.append(f"Includes a {round((1 - discount) * 100)}% longer-rental discount.")
    return {
        "airport": airport.to_dict(), "rental_days": days, "notes": notes,
        "data_status": "demo", "provider": "FlyCompare Demo Cars", "notice": DEMO_NOTICE.format(product="car-rental"),
        "results": offers,
    }


def search_transfers(city: City, airport_code: str | None, on: date, at: time, passengers: int, bags: int, direction: str) -> dict:
    airport = _airport(city, airport_code)
    middle = centre(city)
    # Road distance ≈ 1.3 × straight line; without a known centre, assume a typical airport distance.
    km = max(8.0, round(haversine_km(airport.lat, airport.lon, *middle) * 1.3, 1)) if middle else DEFAULT_AIRPORT_KM
    peak = time(7) <= at <= time(10) or time(16) <= at <= time(20)
    minutes = int(km / (28 if peak else 40) * 60 + 10)
    rng = seeded("transfers", city.key, airport.code, on, direction)
    offers = []
    for kind, vehicle, cap, max_bags, base, per_km, per_person in TRANSFER_TYPES:
        if not per_person and (passengers > cap or bags > max_bags):
            continue
        if per_person and bags > passengers * 2:
            continue
        unit = (base + per_km * km) * _scale(city) * (0.9 + 0.2 * rng.random())
        total = unit * passengers if per_person else unit
        offers.append({
            "id": f"trf-{seeded(city.key, airport.code, vehicle, on, direction).randrange(16**10):010x}",
            "kind": kind, "vehicle": vehicle, "supplier": rng.choice(DEMO_SUPPLIERS),
            "max_passengers": cap if not per_person else None, "max_bags": max_bags if not per_person else 2,
            "distance_km": km,
            "duration_minutes": minutes + (25 if per_person else 0),  # shuttles stop at several hotels
            "meet_and_greet": not per_person,
            "flight_tracking": direction == "from_airport",
            "free_waiting_minutes": (60 if direction == "from_airport" else 15) if not per_person else 0,
            "free_cancellation": "Up to 24 hours before pickup",
            "price_basis": "per person" if per_person else "per vehicle",
            "unit_price": round(unit, 2),
            "total_price": round(total, 2),
            "currency": "USD",
        })
    offers.sort(key=lambda o: o["total_price"])
    return {
        "airport": airport.to_dict(), "distance_km": km, "estimated_minutes": minutes, "peak_traffic": peak,
        "data_status": "demo", "provider": "FlyCompare Demo Transfers", "notice": DEMO_NOTICE.format(product="transfer"),
        "results": offers,
    }
