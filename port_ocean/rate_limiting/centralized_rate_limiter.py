"""Cross-pod centralized rate limiter (Redis + no-op fallback).

Every pod of one integration shares a Redis hash per vendor pool. ``acquire``
decides if this pod may send the next request. ``record_response`` replaces
that hash with the headers from the response that follows.
"""

import time
from typing import Any, cast

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.consumers.redis_client import RedisClient
from port_ocean.consumers.redis_connection import RedisConnectionHelper
from port_ocean.consumers.redis_stream_utils import is_redis_connection_error
from port_ocean.rate_limiting.constants import WAIT_STATUS_INTERVAL_SECONDS
from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    RateLimitBlockReason,
    SyncTier,
)
from port_ocean.rate_limiting.pool_state import (
    PoolRedisState,
    pool_redis_key,
    pool_state_from_redis_hash,
    record_hash_mapping,
    should_back_off_for_sync_tier,
    wait_seconds_until_quota_reset,
    wait_seconds_while_pool_blocked,
)
from port_ocean.rate_limiting.redis_lua_scripts import RESERVE_POOL_SLOT_SCRIPT


class CentralizedRateLimiter:
    """Shared vendor quota for every pod of one integration.

    A Redis client of ``None`` allows every acquire and skips writes. Startup
    does not install that when Redis cannot be reached. It leaves the limiter
    unset so the integration keeps its local limiter.
    """

    def __init__(
        self,
        org_id: str,
        redis_client: RedisClient | None = None,
        redis_connection_helper: RedisConnectionHelper | None = None,
    ) -> None:
        """Store the Port org and the Redis client that holds every pool hash.

        ``org_id`` is the first segment of the Redis key, so two Port orgs
        never share a pool. ``redis_connection_helper`` is kept so ``close``
        can release the connection it opened.
        """
        self._org_id = org_id
        self._redis = redis_client
        self._redis_connection_helper = redis_connection_helper
        self._reserve_sha: str | None = None
        self._status_log_at: dict[str, float] = {}

    async def initialize(self) -> None:
        """Load the reserve script once. Skipped when this limiter has no Redis client."""
        if self._redis is None:
            return
        self._reserve_sha = await self._redis.script_load(RESERVE_POOL_SLOT_SCRIPT)

    async def close(self) -> None:
        """Close Redis and drop the loaded script. Safe to call when setup never connected."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        if self._redis_connection_helper is not None:
            self._redis_connection_helper.cleanup()
            self._redis_connection_helper = None
        self._reserve_sha = None
        self._status_log_at = {}

    @staticmethod
    def _allow() -> AcquireResult:
        """The caller may send the request now."""
        return AcquireResult(decision=RateLimitAcquireDecision.ALLOW)

    @staticmethod
    def _block(
        wait_seconds: float,
        *,
        reason: RateLimitBlockReason,
        state: PoolRedisState,
    ) -> AcquireResult:
        """The caller must wait ``wait_seconds`` and then acquire again.

        A negative wait is clamped to zero. The caller treats zero as "do not
        sleep", so a clock skew cannot stall the pod. ``state`` is the snapshot
        that produced this decision, kept so a status line can still describe
        it if a later read of Redis fails.
        """
        return AcquireResult(
            decision=RateLimitAcquireDecision.BLOCK,
            wait_seconds=max(0.0, wait_seconds),
            reason=reason,
            remaining=state.remaining,
            limit=state.limit,
            reset_at=state.reset_at,
            blocked_until=state.blocked_until,
        )

    def _redis_key_for_pool(self, pool: str) -> str:
        """Hash key ``ratelimit:{org_id}:{integration_identifier}:{pool}``.

        ``pool`` is the vendor bucket (GitHub ``rest`` / ``graphql``, or one
        Azure DevOps organization). Pods of the same integration and pool
        share this key. Other integrations do not.
        """
        return pool_redis_key(self._org_id, ocean.config.integration.identifier, pool)

    def _require_redis(self) -> RedisClient:
        """Return the client. Raises when this limiter was built without one.

        Callers that tolerate a missing client check ``_redis`` first.
        Narrowing here is also what lets ``hgetall`` / ``evalsha`` type-check.
        """
        if self._redis is None:
            raise RuntimeError(
                "Centralized rate limiter Redis client is not initialized"
            )
        return self._redis

    async def _fetch_pool_state(self, key: str) -> PoolRedisState:
        """Read the pool hash. A missing key is an empty snapshot, not an error."""
        raw_hash = await self._require_redis().hgetall(key)
        return pool_state_from_redis_hash(raw_hash)

    def _sleep_seconds_for_pool(self, state: PoolRedisState, now: float) -> float:
        """How long to wait after the reserve script refused this pod.

        A live ``blocked_until`` wins. Otherwise wait until ``reset_at``.
        A past or missing reset yields the 1 second default. Admission does
        not use this for an expired window; it allows that request instead.
        """
        return wait_seconds_while_pool_blocked(
            state.blocked_until, now
        ) or wait_seconds_until_quota_reset(state.reset_at, now)

    def _admission_from_pool(
        self, state: PoolRedisState, tier: SyncTier, now: float
    ) -> AcquireResult | None:
        """Decide from the snapshot alone, before taking a unit of quota.

        Order matters:

        1. ``blocked_until`` in the future is a real 429. Every tier waits
           until that timestamp.
        2. ``reset_at`` missing or already past means the stored remaining
           and limit are stale. Allow the next request so its response can
           write a fresh snapshot. Do not reserve here: remaining is often 0,
           and the script would refuse and spin for 1 second.
        3. While the window is still open, the sync tier may back off until
           ``reset_at``. Full resync yields first, incremental later, and
           live events or actions only when remaining is empty.
        4. No ``limit`` field means this pool has never been published.
           Allow the request.

        ``None`` means the window is open and this tier may spend quota. The
        caller must take one unit with the reserve script.
        """
        blocked_wait = wait_seconds_while_pool_blocked(state.blocked_until, now)
        if blocked_wait is not None:
            return self._block(
                blocked_wait,
                reason=RateLimitBlockReason.BLOCKED_UNTIL,
                state=state,
            )
        # 0 is the stored value when the vendor sent no reset. It is not a future window.
        if state.reset_at <= now:
            return self._allow()
        if should_back_off_for_sync_tier(tier, state):
            return self._block(
                wait_seconds_until_quota_reset(state.reset_at, now),
                reason=RateLimitBlockReason.SYNC_TIER,
                state=state,
            )
        if state.limit is None:
            return self._allow()
        return None

    async def _try_decrement_remaining(self, key: str, now: float) -> bool:
        """Atomically take one unit of ``remaining``.

        Python already applied the tier policy. The script only re-checks
        ``blocked_until`` and decrements, so two pods cannot both take the
        last slot. True when this pod took it. See ``RESERVE_POOL_SLOT_SCRIPT``.
        """
        reserve_sha = self._reserve_sha  # local so mypy sees str, not str | None
        if reserve_sha is None:
            raise RuntimeError("Centralized rate limiter Redis script is not loaded")
        raw: list[Any] = await self._require_redis().evalsha(
            reserve_sha,
            1,
            key,
            str(now),
        )
        return bool(int(raw[0]))

    async def _acquire_with_redis(self, pool: str, tier: SyncTier) -> AcquireResult:
        """Read the pool, apply admission, then reserve a slot if the window is open.

        The script is the race-safe step. If another pod took the last unit
        first, this pod blocks using the snapshot it already read.
        """
        key = self._redis_key_for_pool(pool)
        now = time.time()
        state = await self._fetch_pool_state(key)

        admission = self._admission_from_pool(state, tier, now)
        if admission is not None:
            return admission

        if await self._try_decrement_remaining(key, now):
            return self._allow()

        return self._block(
            self._sleep_seconds_for_pool(state, now),
            reason=RateLimitBlockReason.QUOTA_EXHAUSTED,
            state=state,
        )

    async def acquire(self, pool: str, tier: SyncTier) -> AcquireResult:
        """Return whether this pod may call the vendor for ``pool`` at ``tier``.

        No Redis client allows the request. A dropped Redis connection does
        too, so a Redis outage does not stall outbound calls. Any other error
        propagates.
        """
        if self._redis is None:
            return self._allow()
        try:
            return await self._acquire_with_redis(pool, tier)
        except Exception as error:
            if is_redis_connection_error(error):
                logger.warning(
                    "Centralized rate limiter acquire failed (Redis unavailable); allowing request",
                    error=str(error),
                )
                return self._allow()
            raise

    def _claim_status_log(self, pool: str, now: float) -> bool:
        """True for the first waiter in a pool during each status interval.

        Check and set happen before any await, so concurrent waiters on one
        event loop collapse to a single line per pool per minute.
        """
        last = self._status_log_at.get(pool)
        if last is not None and now - last < WAIT_STATUS_INTERVAL_SECONDS:
            return False
        self._status_log_at[pool] = now
        return True

    async def log_wait_status(
        self,
        pool: str,
        tier: SyncTier,
        result: AcquireResult,
        *,
        sleep_remaining_seconds: float,
    ) -> None:
        """Log the live pool once per minute while callers sleep out a block.

        The sleep itself still lasts for the original ``wait_seconds``. This
        read does not admit a request and does not shorten that sleep. The
        line carries the reason the sleep started and what admission would
        do with the hash as it stands now.
        """
        now = time.time()
        if not self._claim_status_log(pool, now):
            return

        state = self._state_from_acquire_result(result)
        snapshot = "decision"
        if self._redis is not None:
            try:
                state = await self._fetch_pool_state(self._redis_key_for_pool(pool))
                snapshot = "fresh"
            except Exception as error:
                logger.warning(
                    "Centralized rate limiter status read failed; logging the decision snapshot",
                    error=str(error),
                )

        ratio = round(state.remaining / state.limit, 3) if state.limit else None
        reset_in_seconds = round(state.reset_at - now, 3) if state.reset_at else None
        fields = {
            "pool": pool,
            "tier": tier,
            "reason": result.reason,
            "sleep_remaining_seconds": round(sleep_remaining_seconds, 3),
            "decision_wait_seconds": round(result.wait_seconds, 3),
            "remaining": state.remaining,
            "limit": state.limit,
            "ratio": ratio,
            "reset_at": state.reset_at or None,
            "reset_in_seconds": reset_in_seconds,
            "blocked_until": state.blocked_until or None,
            "fresh_admission": self._fresh_admission_label(state, tier, now),
            "snapshot": snapshot,
        }
        detail = " ".join(f"{name}={value}" for name, value in fields.items())
        logger.bind(**fields).info(f"Centralized rate limiter waiting {detail}")

    def _fresh_admission_label(
        self, state: PoolRedisState, tier: SyncTier, now: float
    ) -> str:
        """What a new acquire would do with this snapshot. Does not reserve."""
        fresh = self._admission_from_pool(state, tier, now)
        if fresh is None:
            return "reserve"
        if fresh.decision == RateLimitAcquireDecision.ALLOW:
            return "allow"
        return f"block:{fresh.reason}"

    @staticmethod
    def _state_from_acquire_result(result: AcquireResult) -> PoolRedisState:
        return PoolRedisState(
            limit=result.limit,
            remaining=result.remaining or 0,
            reset_at=result.reset_at or 0.0,
            blocked_until=result.blocked_until or 0.0,
        )

    async def read_pool_state(self, pool: str) -> PoolRedisState | None:
        """Read a pool hash without reserving a slot.

        None when this limiter has no Redis client. A missing key is an
        untracked snapshot (``limit is None``), not None. Callers that must
        not sleep on the pool use this instead of ``acquire``.
        """
        if self._redis is None:
            return None
        return await self._fetch_pool_state(self._redis_key_for_pool(pool))

    async def record_response(
        self,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        """Replace the pool hash with the vendor headers from this response.

        One ``HSET`` writes remaining, limit, reset_at, blocked_until, and
        updated_at together. The hash has no TTL, so the last response stays
        until a later one overwrites it. ``is_rate_limited`` sets
        ``blocked_until`` when the caller did not pass one; that is how a 429
        holds every pod. A Redis failure is logged and ignored so publishing
        quota never fails the HTTP call.
        """
        if self._redis is None:
            return

        key = self._redis_key_for_pool(pool)
        now = time.time()
        mapping = record_hash_mapping(state, is_rate_limited=is_rate_limited, now=now)
        try:
            # redis-py's hset mapping type does not accept dict[str, str].
            await self._require_redis().hset(key, mapping=cast(Any, mapping))
        except Exception as error:
            if is_redis_connection_error(error):
                logger.warning(
                    "Centralized rate limiter record_response failed (Redis unavailable); skipping write",
                    error=str(error),
                )
                return
            logger.warning(
                "Centralized rate limiter record_response error; continuing",
                error=str(error),
            )
