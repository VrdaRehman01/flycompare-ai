"""Build backend/app/data/airports_global.json from open airport datasets.

Sources (download them first, then pass the paths):
  - OurAirports airports.csv and countries.csv — public domain
    https://ourairports.com/data/  (https://davidmegginson.github.io/ourairports-data/)
  - mwgg/Airports airports.json — MIT licence, used only for IANA timezones
    https://github.com/mwgg/Airports

Usage:
  python backend/scripts/build_airport_dataset.py airports.csv countries.csv airports.json

Only airports with an IATA code that are commercially relevant are kept: every
large airport, plus medium/small airports that OurAirports marks as having
scheduled passenger service.
"""

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "airports_global.json"

# Airports whose OurAirports "municipality" is a suburb rather than the city
# travellers search for. Keep this list small and factual.
CITY_OVERRIDES = {
    "BKK": "Bangkok", "DMK": "Bangkok", "NRT": "Tokyo", "HND": "Tokyo", "KIX": "Osaka", "ITM": "Osaka",
    "LHR": "London", "LGW": "London", "STN": "London", "LTN": "London", "LCY": "London", "SEN": "London",
    "CDG": "Paris", "ORY": "Paris", "BVA": "Paris", "JFK": "New York", "LGA": "New York", "EWR": "New York",
    "IAD": "Washington", "DCA": "Washington", "BWI": "Baltimore", "ICN": "Seoul", "GMP": "Seoul",
    "PVG": "Shanghai", "SHA": "Shanghai", "PEK": "Beijing", "PKX": "Beijing", "IST": "Istanbul", "SAW": "Istanbul",
    "DXB": "Dubai", "DWC": "Dubai", "MXP": "Milan", "LIN": "Milan", "BGY": "Milan", "FCO": "Rome", "CIA": "Rome",
    "GRU": "São Paulo", "CGH": "São Paulo", "VCP": "Campinas", "GIG": "Rio de Janeiro", "SDU": "Rio de Janeiro",
    "EZE": "Buenos Aires", "AEP": "Buenos Aires", "CGK": "Jakarta", "HLP": "Jakarta", "KUL": "Kuala Lumpur",
    "SZB": "Kuala Lumpur", "YYZ": "Toronto", "YTZ": "Toronto", "YUL": "Montreal", "SVO": "Moscow", "DME": "Moscow",
    "VKO": "Moscow", "ARN": "Stockholm", "BMA": "Stockholm", "OSL": "Oslo", "CPH": "Copenhagen", "DEL": "Delhi",
    "BOM": "Mumbai", "MAA": "Chennai", "BLR": "Bengaluru", "KHI": "Karachi", "LHE": "Lahore", "ISB": "Islamabad",
    "DOH": "Doha", "AUH": "Abu Dhabi", "JED": "Jeddah", "RUH": "Riyadh", "MNL": "Manila", "SGN": "Ho Chi Minh City",
    "HAN": "Hanoi", "SYD": "Sydney", "MEL": "Melbourne", "AKL": "Auckland", "JNB": "Johannesburg", "CPT": "Cape Town",
    "CAI": "Cairo", "MAD": "Madrid", "BCN": "Barcelona", "FRA": "Frankfurt", "MUC": "Munich", "AMS": "Amsterdam",
    "ZRH": "Zurich", "VIE": "Vienna", "LAX": "Los Angeles", "SFO": "San Francisco", "ORD": "Chicago", "MDW": "Chicago",
    "MIA": "Miami", "FLL": "Fort Lauderdale", "ATL": "Atlanta", "DFW": "Dallas", "DAL": "Dallas", "IAH": "Houston",
    "HOU": "Houston", "SEA": "Seattle", "BOS": "Boston", "MEX": "Mexico City", "NLU": "Mexico City", "HKG": "Hong Kong",
    "TPE": "Taipei", "TSA": "Taipei", "SIN": "Singapore", "MLE": "Malé", "DPS": "Denpasar", "HKT": "Phuket",
    "ATH": "Athens", "VCE": "Venice", "TSF": "Venice", "EDI": "Edinburgh", "NAP": "Naples", "LYS": "Lyon",
    "MRS": "Marseille", "BRU": "Brussels", "CRL": "Brussels", "OTP": "Bucharest", "ZAG": "Zagreb", "LJU": "Ljubljana",
    "KBP": "Kyiv", "TIA": "Tirana", "CFU": "Corfu", "PTY": "Panama City", "ADB": "Izmir", "DMM": "Dammam",
    "EBL": "Erbil", "HEL": "Helsinki", "GOI": "Goa", "GOX": "Goa", "MCT": "Muscat", "NCE": "Nice", "MAN": "Manchester",
    "BHX": "Birmingham", "KEF": "Reykjavik", "RKV": "Reykjavik", "CEB": "Cebu", "PNH": "Phnom Penh",
    "CTU": "Chengdu", "TFU": "Chengdu", "CAN": "Guangzhou", "HAK": "Haikou", "HNL": "Honolulu", "WAW": "Warsaw",
    "WMI": "Warsaw", "BGY": "Milan", "SXF": "Berlin", "TXL": "Berlin", "BCN": "Barcelona", "LIS": "Lisbon",
}


# Airports that OurAirports still lists but which no longer have scheduled
# passenger service (closed, replaced, or business/military only).
NO_PASSENGER_SERVICE = {
    "DIA",  # Doha International: replaced by Hamad (DOH) in 2014
    "TXL", "SXF",  # Berlin Tegel (closed 2020) and Schönefeld (merged into BER)
    "ISL",  # Istanbul Atatürk: passenger flights moved to IST in 2019
    "LBG", "TEB",  # Paris Le Bourget and Teterboro: business aviation only
}


def clean_city(municipality: str) -> str:
    """Normalise OurAirports municipality strings such as "Manchester, Greater
    Manchester", "Guangzhou (Huadu)" or "Muscat/Seeb" to the city name."""
    city = re.sub(r"\s*\([^)]*\)\s*$", "", municipality).strip()
    city = city.split("/")[0].strip()
    if ", " in city:
        city = city.split(", ")[0].strip()
    return city


def main(airports_csv: str, countries_csv: str, mwgg_json: str) -> None:
    countries = {}
    with open(countries_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            countries[row["code"]] = {"name": row["name"], "continent": row["continent"], "keywords": row["keywords"]}

    tz_by_icao, tz_by_iata = {}, {}
    for entry in json.load(open(mwgg_json, encoding="utf-8")).values():
        if entry.get("tz"):
            if entry.get("icao"):
                tz_by_icao[entry["icao"]] = entry["tz"]
            if entry.get("iata"):
                tz_by_iata[entry["iata"]] = entry["tz"]

    airports = []
    seen: set[str] = set()
    with open(airports_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            iata = (row["iata_code"] or "").strip().upper()
            kind = row["type"]
            scheduled = row["scheduled_service"] == "yes"
            if len(iata) != 3 or not iata.isalpha() or iata in seen or iata in NO_PASSENGER_SERVICE:
                continue
            if kind == "large_airport":
                rank = 3
            elif kind == "medium_airport" and scheduled:
                rank = 2
            elif kind == "small_airport" and scheduled:
                rank = 1
            else:
                continue
            country = countries.get(row["iso_country"], {})
            icao = (row["icao_code"] or row["gps_code"] or "").strip().upper() or None
            seen.add(iata)
            airports.append({
                "iata": iata,
                "icao": icao,
                "name": row["name"].strip(),
                "city": CITY_OVERRIDES.get(iata) or clean_city(row["municipality"]) or row["name"].strip(),
                "country_code": row["iso_country"],
                "country": country.get("name", row["iso_country"]),
                "continent": row["continent"],
                "lat": round(float(row["latitude_deg"]), 4),
                "lon": round(float(row["longitude_deg"]), 4),
                "tz": tz_by_icao.get(icao or "") or tz_by_iata.get(iata),
                "rank": rank,
                "keywords": row["keywords"].strip()[:120] or None,
            })

    airports.sort(key=lambda a: (-a["rank"], a["iata"]))
    payload = {
        "source": "OurAirports (public domain) with timezones from mwgg/Airports (MIT)",
        "built": date.today().isoformat(),
        "count": len(airports),
        "countries": {code: {"name": c["name"], "continent": c["continent"]} for code, c in countries.items()},
        "airports": airports,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(airports)} airports to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
