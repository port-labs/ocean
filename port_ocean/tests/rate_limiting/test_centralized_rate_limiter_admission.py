from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import NoScriptError

from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter
from port_ocean.rate_limiting.models import (
    RateLimitAcquireDecision,
    RateLimitBlockReason,
    SyncTier,
)
from port_ocean.rate_limiting.pool_state_utils import PoolRedisState
from port_ocean.rate_limiting.redis_lua_scripts import RESERVE_POOL_SLOT_SCRIPT

NOW = 1_700_000_000.0


def _limiter() -> CentralizedRateLimiter:
    return CentralizedRateLimiter("org-test", AsyncMock(), MagicMock())


def test_expired_quota_allows_even_when_remaining_is_zero() -> None:
    state = PoolRedisState(
        limit=140,
        remaining=0,
        reset_at=NOW - 10,
        blocked_until=0,
    )
    result = _limiter()._admission_from_pool(state, SyncTier.LOW, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.ALLOW


def test_missing_reset_at_allows_instead_of_spinning() -> None:
    state = PoolRedisState(limit=100, remaining=0, reset_at=0, blocked_until=0)
    result = _limiter()._admission_from_pool(state, SyncTier.MEDIUM, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.ALLOW


def test_future_reset_still_backs_off_for_empty_quota() -> None:
    state = PoolRedisState(
        limit=100,
        remaining=0,
        reset_at=NOW + 45,
        blocked_until=0,
    )
    result = _limiter()._admission_from_pool(state, SyncTier.HIGH, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.BLOCK
    assert result.reason == RateLimitBlockReason.SYNC_TIER
    assert result.wait_seconds == 45
    assert result.remaining == 0
    assert result.limit == 100


def test_real_block_holds_after_quota_window_expired() -> None:
    state = PoolRedisState(
        limit=140,
        remaining=0,
        reset_at=NOW - 10,
        blocked_until=NOW + 30,
    )
    result = _limiter()._admission_from_pool(state, SyncTier.HIGH, NOW)
    assert result is not None
    assert result.decision == RateLimitAcquireDecision.BLOCK
    assert result.reason == RateLimitBlockReason.BLOCKED_UNTIL
    assert result.wait_seconds == 30


@pytest.mark.asyncio
async def test_noscript_reloads_script_and_retries_evalsha() -> None:
    redis_client = AsyncMock()
    redis_client.evalsha = AsyncMock(side_effect=[NoScriptError("NOSCRIPT"), [1]])
    redis_client.script_load = AsyncMock(return_value="reloaded-sha")
    limiter = CentralizedRateLimiter("org-test", redis_client, MagicMock())
    limiter._reserve_sha = "startup-sha"

    taken = await limiter._try_decrement_remaining("ratelimit:org:id:pool", NOW)

    assert taken is True
    assert limiter._reserve_sha == "reloaded-sha"
    redis_client.script_load.assert_awaited_once_with(RESERVE_POOL_SLOT_SCRIPT)
    assert redis_client.evalsha.await_count == 2
    first, second = redis_client.evalsha.await_args_list
    assert first.args[0] == "startup-sha"
    assert second.args[0] == "reloaded-sha"


@pytest.mark.asyncio
async def test_noscript_after_reload_propagates() -> None:
    redis_client = AsyncMock()
    redis_client.evalsha = AsyncMock(
        side_effect=[NoScriptError("NOSCRIPT"), NoScriptError("NOSCRIPT")]
    )
    redis_client.script_load = AsyncMock(return_value="reloaded-sha")
    limiter = CentralizedRateLimiter("org-test", redis_client, MagicMock())
    limiter._reserve_sha = "startup-sha"

    with pytest.raises(NoScriptError):
        await limiter._try_decrement_remaining("ratelimit:org:id:pool", NOW)

    redis_client.script_load.assert_awaited_once_with(RESERVE_POOL_SLOT_SCRIPT)
    assert redis_client.evalsha.await_count == 2
