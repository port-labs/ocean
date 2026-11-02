"""Redis pool hash parsing, sync-tier gates, and record field mapping.

These helpers stay here so ``utils`` can import ``CentralizedRateLimiter``
without a cycle: the limiter imports this module, and this module does not
import the limiter.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from port_ocean.rate_limiting.constants import (
    DEFAULT_RATE_LIMITED_BLOCK_SECONDS,
    REDIS_KEY_PREFIX,
)
from port_ocean.rate_limiting.models import CentralizedRateLimitState, SyncTier

# Full resync (SyncTier.LOW) gives way once remaining/limit drops to this.
LOW_REMAINING_RATIO_CEILING = 0.25
# Incremental resync (SyncTier.MEDIUM) gives way one step later.
MEDIUM_REMAINING_RATIO_CEILING = 0.10
# Used only when a caller still wants to wait after reset_at has passed.
# Admission does not: a past reset_at allows the next request instead.
DEFAULT_QUOTA_RESET_WAIT_SECONDS = 1.0


@dataclass(frozen=True)
class PoolRedisState:
    """One pool hash after parsing.

    ``limit`` stays None until a response has published it. That empty
    snapshot is untracked and must not be treated as remaining 0.
    ``reset_at`` and ``blocked_until`` of 0 mean "no timestamp stored".
    """

    limit: int | None
    remaining: int = 0
    reset_at: float = 0.0
    blocked_until: float = 0.0


def decode_redis_hash(raw: Mapping[Any, Any]) -> dict[str, str]:
    """Turn a Redis hash into ``str`` keys and values.

    redis-py returns ``bytes`` when ``decode_responses`` is off. Tests and a
    client with decoding on may already pass ``str``.
    """
    decoded: dict[str, str] = {}
    for key, value in raw.items():
        k = key.decode() if isinstance(key, bytes) else str(key)
        v = value.decode() if isinstance(value, bytes) else str(value)
        decoded[k] = v
    return decoded


def pool_redis_key(org_id: str, integration_identifier: str, pool: str) -> str:
    """``ratelimit:{org_id}:{integration_identifier}:{pool}``.

    ``pool`` splits vendor buckets that do not share a quota, such as GitHub
    ``rest`` and ``graphql``. The key has no TTL; the next response overwrites it.
    """
    return f"{REDIS_KEY_PREFIX}:{org_id}:{integration_identifier}:{pool}"


def wait_seconds_while_pool_blocked(blocked_until: float, now: float) -> float | None:
    """Seconds left in a 429 block, or None when the pool is not blocked.

    None, rather than 0, lets callers use ``or`` to fall through to the
    quota-reset wait. A past ``blocked_until`` is the same as no block.
    """
    if blocked_until > now:
        return blocked_until - now
    return None


def wait_seconds_until_quota_reset(
    reset_at: float,
    now: float,
    *,
    default: float = DEFAULT_QUOTA_RESET_WAIT_SECONDS,
) -> float:
    """Seconds until ``reset_at``, or ``default`` when that time has passed.

    This is a sleep hint for a caller that already decided to wait. It does
    not mean the snapshot is still valid. Admission treats a past ``reset_at``
    as expired and allows the request instead of sleeping for ``default``.
    """
    if reset_at > now:
        return reset_at - now
    return default


def pool_state_from_redis_hash(raw: Mapping[Any, Any]) -> PoolRedisState:
    """Parse a pool hash. A missing key yields an untracked snapshot.

    Remaining is kept only once ``limit`` is present. Without ``limit`` the
    pool has never been published, and a stray ``remaining`` must not look
    like an empty quota. A missing ``reset_at`` becomes 0, which admission
    treats as an expired window.
    """
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
    """Every hash field for one ``HSET``, so a publish cannot tear.

    Redis stores the values as strings. A missing remaining, limit, or
    reset_at is written as ``0``. ``blocked_until`` from the caller wins.
    When the caller omits it, a rate-limited response blocks for
    ``DEFAULT_RATE_LIMITED_BLOCK_SECONDS``; any other response writes ``0``
    and clears a previous 429 hold for every pod.
    """
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
    """Whether this tier should wait out the current vendor window.

    Full resync (``LOW``) backs off at or below 25% remaining. Incremental
    (``MEDIUM``) backs off at or below 10%. Live events and actions
    (``HIGH``) back off only when remaining is empty. No limit, or a limit
    of 0, cannot form a ratio, so those snapshots do not back off.

    ``reset_at`` is ignored here. The caller allows an expired window before
    asking this question.
    """
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
