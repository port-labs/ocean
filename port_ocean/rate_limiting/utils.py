"""Shared helpers for centralized rate limiting."""

import asyncio

from loguru import logger

from port_ocean.context.event import EventType
from port_ocean.context.ocean import ocean
from port_ocean.helpers.sync_tier import _derive_sync_tier
from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter
from port_ocean.rate_limiting.models import (
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    SyncTier,
)


def is_centralized_rate_limiter_enabled() -> bool:
    return ocean.config.centralized_rate_limiter.enabled


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


def active_centralized_rate_limiter() -> CentralizedRateLimiter | None:
    # Enabled check first: a test Ocean may not have the limiter attribute.
    if not ocean.initialized or not is_centralized_rate_limiter_enabled():
        return None
    return ocean.centralized_rate_limiter


def use_centralized_rate_limiting() -> bool:
    """Redis vendor admission/publish when enabled and limiter is active.

    False when disabled or Redis is unavailable (fail-open). Integrations use local
    limiter hooks on the wrapper instead.
    """
    return (
        is_centralized_rate_limiter_enabled()
        and active_centralized_rate_limiter() is not None
    )


async def record_centralized_rate_limit(
    pool: str,
    state: CentralizedRateLimitState,
    *,
    is_rate_limited: bool = False,
) -> None:
    """Publish integration-parsed rate limit state when centralized limiting is active."""
    limiter = active_centralized_rate_limiter()
    if limiter is None:
        return
    await limiter.record_response(pool, state, is_rate_limited=is_rate_limited)


async def await_centralized_rate_limit(pool: str) -> None:
    """Wait for cross-pod admission before sending an outbound request."""
    limiter = active_centralized_rate_limiter()
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

        wait_seconds = result.wait_seconds
        if wait_seconds <= 0:
            return

        await asyncio.sleep(wait_seconds)
