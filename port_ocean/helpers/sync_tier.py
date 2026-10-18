from typing import Optional

from port_ocean.context.event import EventType
from port_ocean.context.ocean import ocean

# One pod runs one mode (a separate pod per incremental sync, full/partial resync,
# actions, and live-events). Background sync backs off slightly harder than
# user-facing work when they share rate-limit pressure on the same token.
# Fixed -- not configurable per RetryConfig instance.
DEFAULT_SYNC_TIER_MULTIPLIERS: dict[str, float] = {
    EventType.RESYNC: 1.15,
    EventType.INCREMENTAL_RESYNC: 1.07,
    EventType.HTTP_REQUEST: 1.01,
    EventType.ACTION_RUN: 1.01,
}


def _derive_sync_tier() -> Optional[str]:
    """Sync tier for this pod, from event-listener settings loaded before RetryConfig
    construction. One flag per mode, checked in order (incremental before plain resync,
    since incremental_sync_enabled is the more specific condition). Returns None when no
    mode matches or settings aren't available (e.g. some test contexts).
    """
    try:
        listener = ocean.config.event_listener
        if ocean.config.integration.incremental_sync_enabled:
            return EventType.INCREMENTAL_RESYNC
        if listener.should_resync:
            return EventType.RESYNC
        if listener.should_process_webhooks:
            return EventType.HTTP_REQUEST
        if listener.should_run_actions:
            return EventType.ACTION_RUN
        return None
    except Exception:
        return None


def derive_sync_tier_multiplier(apply_sync_tier_jitter: bool) -> float:
    """Backoff multiplier for this pod's sync tier (see `_derive_sync_tier`)."""
    if not apply_sync_tier_jitter:
        return 1.0
    tier = _derive_sync_tier()
    if tier is None:
        return 1.0
    return DEFAULT_SYNC_TIER_MULTIPLIERS[tier]
