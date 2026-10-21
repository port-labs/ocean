"""Redis pool hash parsing, sync-tier gates, and record field mapping.

Key and wait helpers live here so utils can import CentralizedRateLimiter
without an import cycle.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from port_ocean.rate_limiting.constants import (
    DEFAULT_RATE_LIMITED_BLOCK_SECONDS,
    REDIS_KEY_PREFIX,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState, SyncTier

LOW_REMAINING_RATIO_CEILING = 0.25
MEDIUM_REMAINING_RATIO_CEILING = 0.10
DEFAULT_QUOTA_RESET_WAIT_SECONDS = 1.0


@dataclass(frozen=True)
class PoolRedisState:
    """Parsed pool hash. ``limit`` is None until integration has written a ``limit`` field."""

    limit: int | None
    remaining: int = 0
    reset_at: float = 0.0
    blocked_until: float = 0.0


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


def pool_state_from_redis_hash(raw: Mapping[Any, Any]) -> PoolRedisState:
    fields = decode_redis_hash(raw)
    limit = int(fields["limit"]) if "limit" in fields else None
    return PoolRedisState(
        limit,
        remaining=int(fields.get("remaining") or 0) if limit is not None else 0,
        reset_at=float(fields.get("reset_at") or 0),
        blocked_until=float(fields.get("blocked_until") or 0),
    )


def record_hash_mapping(
    state: CentralizedRateLimitState,
    *,
    is_rate_limited: bool,
    now: float,
) -> dict[str, str]:
    """Full hash snapshot for one atomic HSET (integrations should pass vendor fields)."""
    blocked_until = state.blocked_until
    if blocked_until is None:
        blocked_until = (
            now + DEFAULT_RATE_LIMITED_BLOCK_SECONDS if is_rate_limited else 0.0
        )

    return {
        "remaining": str(state.remaining if state.remaining is not None else 0),
        "limit": str(state.limit if state.limit is not None else 0),
        "reset_at": str(state.reset_at if state.reset_at is not None else 0),
        "blocked_until": str(blocked_until),
        "updated_at": str(now),
    }


def should_back_off_for_sync_tier(tier: SyncTier, state: PoolRedisState) -> bool:
    if state.limit is None or state.limit <= 0:
        return False
    ratio = state.remaining / state.limit
    if tier == SyncTier.LOW:
        return ratio <= LOW_REMAINING_RATIO_CEILING
    if tier == SyncTier.MEDIUM:
        return ratio <= MEDIUM_REMAINING_RATIO_CEILING
    if tier == SyncTier.HIGH:
        return state.remaining <= 0
    return False
