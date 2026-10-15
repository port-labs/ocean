from port_ocean.context.event import EventType
from port_ocean.helpers.sync_tier import resolve_sync_tier_event_mode
from port_ocean.rate_limiting.models import SyncTier


def derive_sync_tier() -> SyncTier:
    """Map this pod's Ocean event mode to a centralized rate-limit priority tier."""
    mode = resolve_sync_tier_event_mode(True)
    if mode == EventType.RESYNC:
        return SyncTier.LOW
    if mode == EventType.INCREMENTAL_RESYNC:
        return SyncTier.MEDIUM
    if mode in (EventType.HTTP_REQUEST, EventType.ACTION_RUN):
        return SyncTier.HIGH
    return SyncTier.MEDIUM
