"""Weather data from Open-Meteo (https://open-meteo.com): free, no API key, CC BY 4.0.

The adapter returns normalised forecasts; callers never see Open-Meteo's field
names, so another provider can be swapped in behind the same interface.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MAX_FORECAST_DAYS = 16  # Open-Meteo forecasts at most 16 days ahead
BATCH = 50  # locations per request

# WMO weather interpretation codes, as documented by Open-Meteo.
WMO = {
    0: ("Clear sky", "clear"), 1: ("Mainly clear", "clear"), 2: ("Partly cloudy", "partly-cloudy"), 3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"), 48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"), 53: ("Drizzle", "drizzle"), 55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"), 57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"), 66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"), 77: ("Snow grains", "snow"),
    80: ("Rain showers", "rain"), 81: ("Rain showers", "rain"), 82: ("Violent rain showers", "rain"),
    85: ("Snow showers", "snow"), 86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"), 99: ("Thunderstorm with hail", "storm"),
}


class WeatherUnavailable(Exception):
    """The weather provider could not be reached or returned unusable data."""


@dataclass(frozen=True)
class Point:
    key: str
    lat: float
    lon: float


def describe(code: int | None) -> tuple[str, str]:
    return WMO.get(code, ("Unknown", "unknown")) if code is not None else ("Unknown", "unknown")


class OpenMeteoProvider:
    name = "Open-Meteo"
    attribution = "Weather data by Open-Meteo.com (CC BY 4.0)"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 10.0):
        self._client = client
        self._timeout = timeout

    def _get(self, params: dict) -> list[dict]:
        try:
            if self._client is not None:
                response = self._client.get(FORECAST_URL, params=params)
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.get(FORECAST_URL, params=params)
        except httpx.HTTPError as exc:
            raise WeatherUnavailable("Could not reach the weather provider.") from exc
        if response.status_code != 200:
            raise WeatherUnavailable(f"Weather provider returned HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise WeatherUnavailable("Weather provider returned invalid data.") from exc
        return data if isinstance(data, list) else [data]

    def forecast(self, points: list[Point], start: date, days: int = 1) -> dict[str, dict]:
        """Current conditions plus daily forecasts from ``start`` for ``days`` days, per point key."""
        out: dict[str, dict] = {}
        retrieved = datetime.now(timezone.utc).isoformat()
        end = start + timedelta(days=days - 1)
        for i in range(0, len(points), BATCH):
            chunk = points[i:i + BATCH]
            rows = self._get({
                "latitude": ",".join(f"{p.lat:.4f}" for p in chunk),
                "longitude": ",".join(f"{p.lon:.4f}" for p in chunk),
                "current": "temperature_2m,weather_code,is_day",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,snowfall_sum",
                "timezone": "auto",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            })
            if len(rows) != len(chunk):
                raise WeatherUnavailable("Weather provider returned an unexpected number of locations.")
            for point, row in zip(chunk, rows):
                current = row.get("current") or {}
                daily = row.get("daily") or {}
                times = daily.get("time") or []

                def col(name, j):
                    values = daily.get(name) or []
                    return values[j] if j < len(values) else None

                code = current.get("weather_code")
                out[point.key] = {
                    "timezone": row.get("timezone"),
                    "utc_offset_seconds": row.get("utc_offset_seconds"),
                    "current": {
                        "time": current.get("time"),  # local time at the destination
                        "temperature_c": current.get("temperature_2m"),
                        "weather_code": code,
                        "condition": describe(code)[0],
                        "icon": describe(code)[1],
                        "is_day": bool(current.get("is_day")) if current.get("is_day") is not None else None,
                    } if current else None,
                    "daily": [
                        {
                            "date": day,
                            "weather_code": col("weather_code", j),
                            "condition": describe(col("weather_code", j))[0],
                            "icon": describe(col("weather_code", j))[1],
                            "max_c": col("temperature_2m_max", j),
                            "min_c": col("temperature_2m_min", j),
                            "precipitation_mm": col("precipitation_sum", j),
                            "precipitation_probability": col("precipitation_probability_max", j),
                            "snowfall_cm": col("snowfall_sum", j),
                        }
                        for j, day in enumerate(times)
                    ],
                    "retrieved_at": retrieved,
                }
        return out
