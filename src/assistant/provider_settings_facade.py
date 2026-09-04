"""Public provider-settings API consumed by the host application's UI layer.

Keeping this composition boundary in one module prevents the host settings
panel from depending on the assistant package's internal UI and runtime layout.
"""

from src.assistant.runtime.providers.profiles import (
    ProviderProfile,
    ProviderProfileStore,
    ensure_luoda_official_ready,
)
from src.assistant.runtime.providers.router import (
    ProviderResolutionError,
    ProviderRouter,
)
from src.assistant.runtime.providers.secrets import (
    HybridSecretStore,
    ProviderSecretStore,
)
from src.assistant.ui.provider_presentation import (
    provider_connection_badge,
    provider_connection_status_text,
    provider_error_text,
)
from src.assistant.ui.provider_probe_worker import ProviderProbeWorker

__all__ = [
    "HybridSecretStore",
    "ensure_luoda_official_ready",
    "ProviderProbeWorker",
    "ProviderProfile",
    "ProviderProfileStore",
    "ProviderResolutionError",
    "ProviderRouter",
    "ProviderSecretStore",
    "provider_connection_badge",
    "provider_connection_status_text",
    "provider_error_text",
]
