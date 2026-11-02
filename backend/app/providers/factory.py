from app.core.config import Settings
from app.providers.duffel_provider import DuffelFlightProvider, DuffelProviderError
from app.providers.mock_provider import MockDemoFlightProvider


class ProviderConfigError(Exception):
    """The configured provider cannot be constructed."""


def build_flight_provider(settings: Settings) -> tuple[MockDemoFlightProvider | DuffelFlightProvider, str]:
    """Return the provider selected by settings and the data status it produces.

    Outside development only providers returning live data are allowed: simulated
    (mock) or sandbox (Duffel test-token) offers must never reach real users, so the
    search reports itself unavailable instead.
    """
    name = settings.flight_provider.strip().lower()
    if name == "mock":
        provider, data_status = MockDemoFlightProvider(), "demo"
    elif name == "duffel":
        try:
            duffel = DuffelFlightProvider(settings)
        except DuffelProviderError as exc:
            raise ProviderConfigError(str(exc)) from exc
        provider, data_status = duffel, duffel.data_status
    else:
        raise ProviderConfigError(f"Unsupported FLIGHT_PROVIDER value: {name!r}. Use 'mock' or 'duffel'.")
    if data_status != "live" and not settings.is_development:
        raise ProviderConfigError("Flight search is not available right now: no live flight data provider is configured.")
    return provider, data_status
