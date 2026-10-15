from typing import Optional

from port_ocean.context.event import EventType
from port_ocean.context.ocean import ocean

# Fixed multipliers -- see port_ocean.helpers.retry.DEFAULT_SYNC_TIER_MULTIPLIERS
DEFAULT_SYNC_TIER_MULTIPLIERS: dict[Optional[str], float] = {
    EventType.RESYNC: 1.15,
    EventType.INCREMENTAL_RESYNC: 1.07,
    EventType.HTTP_REQUEST: 1.01,
    EventType.ACTION_RUN: 1.01,
}


def resolve_sync_tier_event_mode(apply_sync_tier_jitter: bool = True) -> Optional[str]:
    if not apply_sync_tier_jitter:
        return None
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
    if not apply_sync_tier_jitter:
        return 1.0
    mode = resolve_sync_tier_event_mode(True)
    if mode is None:
        return 1.0
    return DEFAULT_SYNC_TIER_MULTIPLIERS.get(mode, 1.0)
