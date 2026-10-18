"""Shared helpers for centralized rate limiting."""

import asyncio
from typing import Any, Mapping

from loguru import logger

from port_ocean.context.event import EventType
from port_ocean.context.ocean import ocean
from port_ocean.helpers.sync_tier import _derive_sync_tier
from port_ocean.rate_limiting.constants import REDIS_KEY_PREFIX
from port_ocean.rate_limiting.models import (
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    SyncTier,
)

DEFAULT_QUOTA_RESET_WAIT_SECONDS = 1.0


def is_centralized_rate_limiter_enabled() -> bool:
    return ocean.config.centralized_rate_limiter.enabled


def decode_redis_hash(raw: Mapping[Any, Any]) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for key, value in raw.items():
        k = key.decode() if isinstance(key, bytes) else str(key)
        v = value.decode() if isinstance(value, bytes) else str(value)
        decoded[k] = v
    return decoded


def pool_redis_key(org_id: str, integration_identifier: str, pool: str) -> str:
    return f"{REDIS_KEY_PREFIX}:{org_id}:{integration_identifier}:{pool}"


def wait_seconds_while_pool_blocked(blocked_until: float, now: float) -> float | None:
    """Seconds left in a vendor block window, or None if not blocked."""
    if blocked_until > now:
        return blocked_until - now
    return None


def wait_seconds_until_quota_reset(
    reset_at: float,
    now: float,
    *,
    default: float = DEFAULT_QUOTA_RESET_WAIT_SECONDS,
) -> float:
    """Sleep hint when quota is tight: vendor reset time, or a small default."""
    if reset_at > now:
        return reset_at - now
    return default


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


def active_centralized_rate_limiter():
    if (
        not ocean.initialized
        or ocean.centralized_rate_limiter is None
        or not is_centralized_rate_limiter_enabled()
    ):
        return None
    return ocean.centralized_rate_limiter


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

        logger.debug(
            "Centralized rate limiter blocked request",
            pool=pool,
            tier=tier.value,
            wait_seconds=wait_seconds,
        )
        await asyncio.sleep(wait_seconds)
