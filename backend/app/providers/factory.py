from app.core.config import Settings
from app.providers.duffel_provider import DuffelFlightProvider
from app.providers.errors import FlightProviderError
from app.providers.mock_provider import MockDemoFlightProvider
from app.providers.travelpayouts_provider import TravelpayoutsFlightProvider

FlightProvider = MockDemoFlightProvider | DuffelFlightProvider | TravelpayoutsFlightProvider
# Real market data: live offers, or recent fares found by real users. Never demo or sandbox.
REAL_DATA = {"live", "recent"}


class ProviderConfigError(Exception):
    """The configured provider cannot be constructed."""


def build_flight_provider(settings: Settings) -> tuple[FlightProvider, str]:
    """Return the provider selected by settings and the data status it produces.

    Outside development only providers returning real data are allowed: simulated
    (mock) or sandbox (Duffel test-token) offers must never reach real users, so the
    search reports itself unavailable instead.
    """
    name = settings.flight_provider.strip().lower()
    try:
        if name == "mock":
            provider: FlightProvider = MockDemoFlightProvider()
            data_status = "demo"
        elif name == "duffel":
            provider = DuffelFlightProvider(settings)
            data_status = provider.data_status
        elif name == "travelpayouts":
            provider = TravelpayoutsFlightProvider(settings)
            data_status = provider.data_status
        else:
            raise ProviderConfigError(f"Unsupported FLIGHT_PROVIDER value: {name!r}. Use 'mock', 'duffel' or 'travelpayouts'.")
    except FlightProviderError as exc:
        raise ProviderConfigError(str(exc)) from exc
    if data_status not in REAL_DATA and not settings.is_development:
        raise ProviderConfigError("Flight search is not available right now: no live flight data provider is configured.")
    return provider, data_status
