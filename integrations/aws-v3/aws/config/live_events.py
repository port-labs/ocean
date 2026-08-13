import os

from port_ocean.context.ocean import ocean

LIVE_EVENTS_API_KEY_ENV = "OCEAN__INTEGRATION__CONFIG__LIVE_EVENTS_API_KEY"


def get_live_events_api_key() -> str | None:
    """Return the live-events API key from integration config or local env fallback.

    ``liveEventsApiKey`` is intentionally omitted from ``spec.yaml`` (hidden from Port UI
    while live events are not released yet). The dynamic config model built from spec
    may therefore drop the key when parsing env vars on older Ocean versions; read the env
    var directly as a fallback for local development.
    """
    configured_key = ocean.integration_config.get("live_events_api_key")
    if configured_key:
        return str(configured_key)
    env_key = os.environ.get(LIVE_EVENTS_API_KEY_ENV)
    return env_key if env_key else None
