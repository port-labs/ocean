"""Cross-pod centralized rate limiter.

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
from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    RateLimitBlockReason,
    SyncTier,
)
from port_ocean.rate_limiting.pool_state_utils import (
    PoolRedisState,
    pool_redis_key,
    pool_state_from_redis_hash,
    record_hash_mapping,
    wait_seconds_until_quota_reset,
    wait_seconds_while_pool_blocked,
)
from port_ocean.rate_limiting.redis_lua_scripts import RESERVE_POOL_SLOT_SCRIPT


class CentralizedRateLimiter:
    """Shared vendor quota for every pod of one integration.

    Startup installs this only after Redis is connected. A dropped connection
    during acquire allows that one request. A failed publish is logged and
    ignored.
    """

    def __init__(
        self,
        org_id: str,
        redis_client: RedisClient,
        redis_connection_helper: RedisConnectionHelper,
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

    async def initialize(self) -> None:
        """Load the reserve script once."""
        self._reserve_sha = await self._redis.script_load(RESERVE_POOL_SLOT_SCRIPT)

    async def close(self) -> None:
        """Close Redis and remove the temporary TLS files."""
        await self._redis.aclose()
        self._redis_connection_helper.cleanup()
        self._reserve_sha = None

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
        sleep", so a clock skew cannot stall the pod.
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

    async def _fetch_pool_state(self, key: str) -> PoolRedisState:
        """Read the pool hash. A missing key is an empty snapshot, not an error."""
        raw_hash = await self._redis.hgetall(key)
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
        if state.should_back_off(tier):
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
        raw: list[Any] = await self._redis.evalsha(
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

        A dropped Redis connection allows the request, so a Redis outage does
        not stall outbound calls. Any other error propagates.
        """
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

    async def record_response(
        self,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        """Publish this response onto the pool hash.

        One ``HSET`` writes the quota fields this response actually carried,
        plus ``blocked_until`` and ``updated_at``. Missing remaining, limit,
        or reset_at are left untouched. The hash has no TTL, so the last
        write stays until a later one updates it. ``is_rate_limited`` sets
        ``blocked_until`` when the caller did not pass one; that is how a 429
        holds every pod. A Redis failure is logged and ignored so publishing
        quota never fails the HTTP call.
        """
        key = self._redis_key_for_pool(pool)
        now = time.time()
        mapping = record_hash_mapping(state, is_rate_limited=is_rate_limited, now=now)
        try:
            # redis-py's hset mapping type does not accept dict[str, str].
            await self._redis.hset(key, mapping=cast(Any, mapping))
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
