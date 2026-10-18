"""Cross-pod centralized rate limiter (Redis + no-op fallback)."""

import time
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from port_ocean.context.ocean import ocean
from port_ocean.consumers.redis_connection import RedisConnectionHelper
from port_ocean.consumers.redis_stream_utils import is_redis_connection_error
from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    SyncTier,
)
from port_ocean.rate_limiting.pool_state import (
    PoolRedisState,
    pool_state_from_redis_hash,
    record_hash_mapping,
    should_back_off_for_sync_tier,
)
from port_ocean.rate_limiting.redis_lua_scripts import RESERVE_POOL_SLOT_SCRIPT
from port_ocean.rate_limiting.utils import (
    pool_redis_key,
    wait_seconds_until_quota_reset,
    wait_seconds_while_pool_blocked,
)


class CentralizedRateLimiter:
    """Acquire and record shared API pool state in Redis."""

    def __init__(
        self,
        org_id: str,
        redis_client: Redis | None = None,
        redis_connection_helper: RedisConnectionHelper | None = None,
    ) -> None:
        if not org_id:
            raise ValueError("org_id must be non-empty")
        self._org_id = org_id
        self._redis = redis_client
        self._redis_connection_helper = redis_connection_helper
        self._reserve_sha: str | None = None

    async def initialize(self) -> None:
        if self._redis is None:
            return
        self._reserve_sha = await self._redis.script_load(RESERVE_POOL_SLOT_SCRIPT)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        if self._redis_connection_helper is not None:
            self._redis_connection_helper.cleanup()
            self._redis_connection_helper = None
        self._reserve_sha = None

    @staticmethod
    def _allow() -> AcquireResult:
        return AcquireResult(decision=RateLimitAcquireDecision.ALLOW)

    @staticmethod
    def _block(wait_seconds: float) -> AcquireResult:
        return AcquireResult(
            decision=RateLimitAcquireDecision.BLOCK,
            wait_seconds=max(0.0, wait_seconds),
        )

    def _redis_key_for_pool(self, pool: str) -> str:
        return pool_redis_key(self._org_id, ocean.config.integration.identifier, pool)

    async def _fetch_pool_state(self, key: str) -> PoolRedisState:
        raw_hash = await self._redis.hgetall(key)
        return pool_state_from_redis_hash(raw_hash)

    def _sleep_seconds_for_pool(self, state: PoolRedisState, now: float) -> float:
        return wait_seconds_while_pool_blocked(
            state.blocked_until, now
        ) or wait_seconds_until_quota_reset(state.reset_at, now)

    def _admission_from_pool(
        self, state: PoolRedisState, tier: SyncTier, now: float
    ) -> AcquireResult | None:
        """Allow or block from pool snapshot; None means caller should run reserve Lua."""
        blocked_wait = wait_seconds_while_pool_blocked(state.blocked_until, now)
        if blocked_wait is not None:
            return self._block(blocked_wait)
        if should_back_off_for_sync_tier(tier, state):
            return self._block(wait_seconds_until_quota_reset(state.reset_at, now))
        if state.limit is None:
            return self._allow()
        return None

    async def _try_decrement_remaining(self, key: str, now: float) -> bool:
        """Reserve Lua returns 1 if a slot was taken, 0 otherwise (see RESERVE_POOL_SLOT_SCRIPT)."""
        raw: list[Any] = await self._redis.evalsha(
            self._reserve_sha,
            1,
            key,
            str(now),
        )
        return bool(int(raw[0]))

    async def _acquire_with_redis(self, pool: str, tier: SyncTier) -> AcquireResult:
        key = self._redis_key_for_pool(pool)
        now = time.time()
        state = await self._fetch_pool_state(key)

        admission = self._admission_from_pool(state, tier, now)
        if admission is not None:
            return admission

        if await self._try_decrement_remaining(key, now):
            return self._allow()

        return self._block(self._sleep_seconds_for_pool(state, now))

    async def acquire(self, pool: str, tier: SyncTier) -> AcquireResult:
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

    async def record_response(
        self,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        if self._redis is None:
            return

        key = self._redis_key_for_pool(pool)
        now = time.time()
        mapping = record_hash_mapping(state, is_rate_limited=is_rate_limited, now=now)
        try:
            await self._redis.hset(key, mapping=mapping)
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
