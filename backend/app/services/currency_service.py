"""Exchange rates from the European Central Bank reference rates (via Frankfurter).

Rates are informational, published once per working day, and cover about 30
currencies. When a fallback source is configured (ExchangeRate-API's open
endpoint), it fills in currencies the ECB does not publish, such as PKR, AED
and SAR; ECB rates always win where both publish. Currencies neither source
publishes are reported as unsupported rather than guessed.
"""

import threading
import time

import httpx

from app.core.config import get_settings

ECB_SOURCE = "European Central Bank reference rates (via Frankfurter)"
FALLBACK_SOURCE = "ExchangeRate-API (open.er-api.com)"


class CurrencyUnavailable(Exception):
    pass


_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def _numeric(rates: object) -> dict[str, float]:
    if not isinstance(rates, dict):
        return {}
    return {k: float(v) for k, v in rates.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _fetch_ecb(client: httpx.Client, base: str) -> tuple[str | None, dict[str, float]]:
    settings = get_settings()
    response = client.get(f"{settings.currency_api_url.rstrip('/')}/latest", params={"base": base})
    if response.status_code == 404 or response.status_code == 422:
        raise CurrencyUnavailable(f"Exchange rates are not published for {base}.")
    response.raise_for_status()
    payload = response.json()
    return payload.get("date"), _numeric(payload.get("rates"))


def _fetch_fallback(client: httpx.Client, base: str) -> tuple[str | None, dict[str, float]]:
    settings = get_settings()
    response = client.get(f"{settings.currency_fallback_api_url.rstrip('/')}/{base}")
    response.raise_for_status()
    payload = response.json()
    if payload.get("result") != "success":
        raise CurrencyUnavailable(f"Exchange rates are not published for {base}.")
    updated = payload.get("time_last_update_utc")
    rates = _numeric(payload.get("rates"))
    rates.pop(base, None)
    return (str(updated) if updated else None), rates


def get_rates(base: str) -> dict:
    settings = get_settings()
    base = base.upper()
    now = time.time()
    with _lock:
        cached = _cache.get(base)
        if cached and now - cached[0] < settings.currency_cache_seconds:
            return cached[1]

    ecb_date, ecb_rates, ecb_error = None, {}, None
    fb_date, fb_rates = None, {}
    with httpx.Client(timeout=settings.currency_timeout_seconds) as client:
        try:
            ecb_date, ecb_rates = _fetch_ecb(client, base)
        except CurrencyUnavailable as exc:
            ecb_error = exc
        except httpx.HTTPError as exc:
            ecb_error = CurrencyUnavailable("Exchange rates are unavailable right now.")
            ecb_error.__cause__ = exc
        except ValueError as exc:
            ecb_error = CurrencyUnavailable("Exchange-rate service returned an unexpected response.")
            ecb_error.__cause__ = exc
        if settings.currency_fallback_api_url:
            try:
                fb_date, fb_rates = _fetch_fallback(client, base)
            except (CurrencyUnavailable, httpx.HTTPError, ValueError):
                fb_rates = {}

    if not ecb_rates and not fb_rates:
        raise ecb_error or CurrencyUnavailable(f"Exchange rates are not published for {base}.")

    extra = {k: v for k, v in fb_rates.items() if k not in ecb_rates}
    if ecb_rates and extra:
        source = f"{ECB_SOURCE}; other currencies from {FALLBACK_SOURCE}"
    elif ecb_rates:
        source = ECB_SOURCE
    else:
        source = FALLBACK_SOURCE
    result = {
        "base": base,
        "date": ecb_date or fb_date,
        "source": source,
        "rates": {**extra, **ecb_rates},
    }
    with _lock:
        _cache[base] = (now, result)
    return result


def clear_cache() -> None:
    with _lock:
        _cache.clear()
