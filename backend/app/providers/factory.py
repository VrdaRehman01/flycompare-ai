from app.core.config import Settings
from app.providers.duffel_provider import DuffelFlightProvider, DuffelProviderError
from app.providers.mock_provider import MockDemoFlightProvider


class ProviderConfigError(Exception):
    """The configured provider cannot be constructed."""


def build_flight_provider(settings: Settings) -> tuple[MockDemoFlightProvider | DuffelFlightProvider, str]:
    """Return the provider selected by settings and the data status it produces."""
    name = settings.flight_provider.strip().lower()
    if name == "mock":
        return MockDemoFlightProvider(), "demo"
    if name == "duffel":
        try:
            provider = DuffelFlightProvider(settings)
        except DuffelProviderError as exc:
            raise ProviderConfigError(str(exc)) from exc
        return provider, provider.data_status
    raise ProviderConfigError(f"Unsupported FLIGHT_PROVIDER value: {name!r}. Use 'mock' or 'duffel'.")
