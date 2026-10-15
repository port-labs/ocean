import time
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from port_ocean.consumers.redis_stream_utils import is_redis_connection_error
from port_ocean.rate_limiting.backend import CentralizedRateLimiterBackend
from port_ocean.rate_limiting.constants import REDIS_KEY_PREFIX
from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    SyncTier,
)

_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local tier = ARGV[1]
local now = tonumber(ARGV[2])

local blocked = redis.call('HGET', key, 'blocked_until')
if blocked then
  local blocked_until = tonumber(blocked)
  if blocked_until and blocked_until > now then
    return {0, tostring(blocked_until - now)}
  end
end

local remaining = redis.call('HGET', key, 'remaining')
local limit = redis.call('HGET', key, 'limit')
local reset_at = redis.call('HGET', key, 'reset_at')

if remaining and limit then
  local rem = tonumber(remaining)
  local lim = tonumber(limit)
  if lim and lim > 0 and rem ~= nil then
    local ratio = rem / lim
    if tier == 'low' and ratio <= 0.40 then
      local wait = 1
      if reset_at then
        local reset = tonumber(reset_at)
        if reset and reset > now then
          wait = reset - now
        end
      end
      return {0, tostring(wait)}
    end
    if tier == 'medium' and ratio <= 0.10 then
      local wait = 1
      if reset_at then
        local reset = tonumber(reset_at)
        if reset and reset > now then
          wait = reset - now
        end
      end
      return {0, tostring(wait)}
    end
    if tier == 'high' and rem <= 0 then
      local wait = 1
      if reset_at then
        local reset = tonumber(reset_at)
        if reset and reset > now then
          wait = reset - now
        end
      end
      return {0, tostring(wait)}
    end
    redis.call('HINCRBY', key, 'remaining', -1)
  end
end

return {1, '0'}
"""

_RECORD_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local is_rate_limited = ARGV[2] == '1'

if ARGV[3] ~= '' then
  redis.call('HSET', key, 'remaining', ARGV[3])
end
if ARGV[4] ~= '' then
  redis.call('HSET', key, 'limit', ARGV[4])
end
if ARGV[5] ~= '' then
  redis.call('HSET', key, 'reset_at', ARGV[5])
end
if ARGV[6] ~= '' then
  redis.call('HSET', key, 'blocked_until', ARGV[6])
elseif is_rate_limited then
  redis.call('HSET', key, 'blocked_until', tostring(now + 60))
end
redis.call('HSET', key, 'updated_at', tostring(now))
return 1
"""


class RedisCentralizedRateLimiterBackend(CentralizedRateLimiterBackend):
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
        self._acquire_sha: str | None = None
        self._record_sha: str | None = None

    def _pool_key(self, org_scope: str, integration_id: str, pool: str) -> str:
        return f"{REDIS_KEY_PREFIX}:{org_scope}:{integration_id}:{pool}"

    async def _ensure_scripts(self) -> None:
        if self._acquire_sha is None:
            self._acquire_sha = await self._redis.script_load(_ACQUIRE_SCRIPT)
        if self._record_sha is None:
            self._record_sha = await self._redis.script_load(_RECORD_SCRIPT)

    async def acquire(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        tier: SyncTier,
    ) -> AcquireResult:
        await self._ensure_scripts()
        key = self._pool_key(org_scope, integration_id, pool)
        now = time.time()
        try:
            result: list[Any] = await self._redis.evalsha(
                self._acquire_sha,
                1,
                key,
                tier.value,
                str(now),
            )
        except Exception as error:
            if is_redis_connection_error(error):
                logger.warning(
                    "Centralized rate limiter acquire failed (Redis unavailable); allowing request",
                    error=str(error),
                )
                return AcquireResult(decision=RateLimitAcquireDecision.ALLOW)
            raise

        allowed = int(result[0]) == 1
        wait_seconds = float(result[1]) if len(result) > 1 else 0.0
        if allowed:
            return AcquireResult(decision=RateLimitAcquireDecision.ALLOW)
        return AcquireResult(
            decision=RateLimitAcquireDecision.BLOCK,
            wait_seconds=max(0.0, wait_seconds),
        )

    async def record_response(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        await self._ensure_scripts()
        key = self._pool_key(org_scope, integration_id, pool)
        now = time.time()

        def field(value: int | float | None) -> str:
            return "" if value is None else str(value)

        try:
            await self._redis.evalsha(
                self._record_sha,
                1,
                key,
                str(now),
                "1" if is_rate_limited else "0",
                field(state.remaining),
                field(state.limit),
                field(state.reset_at),
                field(state.blocked_until),
            )
        except Exception as error:
            if is_redis_connection_error(error):
                logger.warning(
                    "Centralized rate limiter record_response failed (Redis unavailable); skipping write",
                    error=str(error),
                )
                return
            raise
