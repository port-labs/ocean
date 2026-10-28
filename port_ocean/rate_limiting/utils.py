"""Shared helpers for centralized rate limiting."""

import asyncio

from loguru import logger

from port_ocean.context.event import EventType
from port_ocean.context.ocean import ocean
from port_ocean.helpers.sync_tier import _derive_sync_tier
from port_ocean.rate_limiting.models import (
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    SyncTier,
)


def derive_sync_tier() -> SyncTier:
    """Map this pod's Ocean event mode to a centralized rate-limit priority tier."""
    mode = _derive_sync_tier()
    if mode == EventType.RESYNC:
        return SyncTier.LOW
    if mode == EventType.INCREMENTAL_RESYNC:
        return SyncTier.MEDIUM
    if mode in (EventType.HTTP_REQUEST, EventType.ACTION_RUN):
        return SyncTier.HIGH
    return SyncTier.MEDIUM


def use_centralized_rate_limiting() -> bool:
    """True when this process should use Redis admission instead of the local limiter.

    False when setup left the limiter unset. A Redis connection failure at
    startup does that, so the wrapper keeps the local limiter.
    """
    return ocean.centralized_rate_limiter is not None


async def record_centralized_rate_limit(
    pool: str,
    state: CentralizedRateLimitState,
    *,
    is_rate_limited: bool = False,
) -> None:
    """Publish integration-parsed rate limit state when centralized limiting is active."""
    limiter = ocean.centralized_rate_limiter
    if limiter is None:
        return
    await limiter.record_response(pool, state, is_rate_limited=is_rate_limited)


async def await_centralized_rate_limit(pool: str) -> None:
    """Wait for cross-pod admission before sending an outbound request.

    A block sleeps for the full ``wait_seconds`` from that acquire, then
    asks again.
    """
    limiter = ocean.centralized_rate_limiter
    if limiter is None:
        return

    tier = derive_sync_tier()

    while True:
        try:
            result = await limiter.acquire(pool, tier)
        except Exception as error:
            logger.warning(
                "Centralized rate limiter acquire error; allowing request",
                error=str(error),
            )
            return

        if result.decision == RateLimitAcquireDecision.ALLOW:
            return

        if result.wait_seconds <= 0:
            return

        await asyncio.sleep(result.wait_seconds)
