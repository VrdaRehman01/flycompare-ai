"""Weather discovery: provider normalisation, category rules, date limits. No network access."""

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.providers.weather_provider import OpenMeteoProvider, Point, WeatherUnavailable
from app.services import weather_service


@pytest.fixture(autouse=True)
def clear_cache():
    weather_service._cache.clear()
    yield
    weather_service._cache.clear()


def open_meteo_row(max_c=30.0, code=0, rain=0.0, snow=0.0):
    return {
        "timezone": "Asia/Dubai", "utc_offset_seconds": 14400,
        "current": {"time": "2026-10-31T21:30", "temperature_2m": 28.2, "weather_code": code, "is_day": 0},
        "daily": {"time": ["2026-10-31"], "weather_code": [code], "temperature_2m_max": [max_c], "temperature_2m_min": [20.0],
                  "precipitation_sum": [rain], "precipitation_probability_max": [5], "snowfall_sum": [snow]},
    }


class FakeClient:
    def __init__(self, rows=None, status=200):
        self.rows, self.status, self.calls = rows, status, []

    def get(self, url, params=None):
        self.calls.append(params)
        n = len(params["latitude"].split(","))
        rows = self.rows if self.rows is not None else [open_meteo_row() for _ in range(n)]
        return httpx.Response(self.status, json=rows if n > 1 else rows[0], request=httpx.Request("GET", url))


def test_provider_normalises_open_meteo_fields():
    data = OpenMeteoProvider(FakeClient()).forecast([Point("Dubai|AE", 25.2, 55.3)], date(2026, 10, 31))
    d = data["Dubai|AE"]
    assert d["current"]["temperature_c"] == 28.2 and d["current"]["condition"] == "Clear sky" and d["current"]["is_day"] is False
    assert d["daily"][0] == {"date": "2026-10-31", "weather_code": 0, "condition": "Clear sky", "icon": "clear", "max_c": 30.0,
                             "min_c": 20.0, "precipitation_mm": 0.0, "precipitation_probability": 5, "snowfall_cm": 0.0}
    assert d["timezone"] == "Asia/Dubai"


def test_provider_errors_are_reported_not_invented():
    with pytest.raises(WeatherUnavailable):
        OpenMeteoProvider(FakeClient(status=500)).forecast([Point("x", 0, 0)], date(2026, 10, 31))


def test_many_locations_are_batched():
    client = FakeClient()
    OpenMeteoProvider(client).forecast([Point(str(i), 0, 0) for i in range(120)], date(2026, 10, 31))
    assert len(client.calls) == 3


@pytest.mark.parametrize("day, themes, expected", [
    ({"icon": "clear", "max_c": 31, "precipitation_mm": 0, "snowfall_cm": 0}, ("Beach",), ["sunny", "warm", "beach"]),
    ({"icon": "rain", "max_c": 31, "precipitation_mm": 8, "snowfall_cm": 0}, ("Beach",), ["warm", "rainy"]),
    ({"icon": "snow", "max_c": -2, "precipitation_mm": 1, "snowfall_cm": 3}, ("City",), ["snow"]),
    ({"icon": "partly-cloudy", "max_c": 21, "precipitation_mm": 0, "snowfall_cm": 0}, ("City", "Culture"), ["sunny", "city"]),
    # A brief shower (low chance, little rain) does not make the day rainy.
    ({"icon": "rain", "max_c": 22, "precipitation_mm": 0.4, "precipitation_probability": 20, "snowfall_cm": 0}, ("City",), ["city"]),
    ({"icon": "cloudy", "max_c": 12, "precipitation_mm": 0, "snowfall_cm": 0}, ("Nature",), ["cool"]),
    ({"icon": "unknown", "max_c": None, "precipitation_mm": None, "snowfall_cm": None}, ("Beach",), []),  # missing data matches nothing
])
def test_category_rules(day, themes, expected):
    assert weather_service.categorise(day, themes) == expected


def test_discover_rejects_dates_beyond_the_forecast_range(db_session):
    far = date.today() + timedelta(days=30)
    result = weather_service.discover(db_session, far, provider=OpenMeteoProvider(FakeClient()))
    assert result["available"] is False and "16 days" in result["reason"]
    assert weather_service.discover(db_session, date.today() - timedelta(days=1), provider=OpenMeteoProvider(FakeClient()))["available"] is False


def test_discover_today_is_current_and_cached(db_session):
    client = FakeClient()
    provider = OpenMeteoProvider(client)
    result = weather_service.discover(db_session, provider=provider)
    assert result["available"] and result["kind"] == "current" and result["items"]
    item = result["items"][0]
    assert item["current"]["temperature_c"] == 28.2 and item["fare"] is None
    calls = len(client.calls)
    weather_service.discover(db_session, provider=provider)
    assert len(client.calls) == calls  # served from cache


def test_discover_future_day_is_labelled_forecast(db_session):
    result = weather_service.discover(db_session, date.today() + timedelta(days=3), provider=OpenMeteoProvider(FakeClient()))
    assert result["kind"] == "forecast" and result["items"][0]["current"] is None



def test_today_for_timezone_handles_utc_calendar_boundary():
    # At 20:30 UTC on Oct 31, it is already Nov 1 in Karachi (UTC+5).
    utc_now = datetime(2026, 10, 31, 20, 30, tzinfo=timezone.utc)
    assert weather_service.today_for_timezone(-300, utc_now) == date(2026, 11, 1)
    # UTC+10 local time is still Oct 31 at the same UTC instant.
    assert weather_service.today_for_timezone(-600, utc_now) == date(2026, 11, 1)
    # UTC-5 is still Oct 31.
    assert weather_service.today_for_timezone(300, utc_now) == date(2026, 10, 31)

def test_endpoint_reports_provider_failure_honestly(client, monkeypatch):
    monkeypatch.setattr(weather_service, "OpenMeteoProvider", lambda: OpenMeteoProvider(FakeClient(status=503)))
    body = client.get("/api/weather/discover").json()
    assert body["available"] is False and "try again" in body["reason"]
    assert client.get("/api/weather/discover?origin=ZZZ").status_code in (404, 422)
