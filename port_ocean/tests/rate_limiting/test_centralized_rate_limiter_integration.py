from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger

from port_ocean.rate_limiting.centralized_rate_limiter import CentralizedRateLimiter
from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    RateLimitBlockReason,
    SyncTier,
)
from port_ocean.rate_limiting.pool_state import PoolRedisState
from port_ocean.rate_limiting.utils import (
    active_centralized_rate_limiter,
    await_centralized_rate_limit,
    record_centralized_rate_limit,
)


@pytest.mark.asyncio
async def test_record_centralized_rate_limit_calls_limiter() -> None:
    state = CentralizedRateLimitState(remaining=10, limit=100)
    mock_limiter = MagicMock()
    mock_limiter.record_response = AsyncMock()

    with patch(
        "port_ocean.rate_limiting.utils.active_centralized_rate_limiter",
        return_value=mock_limiter,
    ):
        await record_centralized_rate_limit(
            "github_rest",
            state,
            is_rate_limited=True,
        )

    mock_limiter.record_response.assert_awaited_once_with(
        "github_rest",
        state,
        is_rate_limited=True,
    )


@pytest.mark.asyncio
async def test_record_centralized_rate_limit_noop_when_inactive() -> None:
    with patch(
        "port_ocean.rate_limiting.utils.active_centralized_rate_limiter",
        return_value=None,
    ):
        await record_centralized_rate_limit(
            "default",
            CentralizedRateLimitState(remaining=1, limit=1),
        )


@pytest.mark.asyncio
async def test_await_centralized_rate_limit_logs_every_minute_of_a_block() -> None:
    blocked = AcquireResult(
        decision=RateLimitAcquireDecision.BLOCK,
        wait_seconds=125,
        reason=RateLimitBlockReason.SYNC_TIER,
        remaining=40,
        limit=184,
        reset_at=1_700_000_295.0,
    )
    allowed = AcquireResult(decision=RateLimitAcquireDecision.ALLOW)
    mock_limiter = MagicMock()
    mock_limiter.acquire = AsyncMock(side_effect=[blocked, allowed])
    mock_limiter.log_wait_status = AsyncMock()

    with (
        patch(
            "port_ocean.rate_limiting.utils.active_centralized_rate_limiter",
            return_value=mock_limiter,
        ),
        patch(
            "port_ocean.rate_limiting.utils.derive_sync_tier",
            return_value=SyncTier.LOW,
        ),
        patch(
            "port_ocean.rate_limiting.utils.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
    ):
        await await_centralized_rate_limit("ocean-sandbox")

    assert [call.args[0] for call in sleep.await_args_list] == [60, 60, 5]
    assert mock_limiter.log_wait_status.await_count == 3
    first = mock_limiter.log_wait_status.await_args_list[0]
    assert first.args[:3] == ("ocean-sandbox", SyncTier.LOW, blocked)
    assert first.kwargs["sleep_remaining_seconds"] == 125
    last = mock_limiter.log_wait_status.await_args_list[-1]
    assert last.kwargs["sleep_remaining_seconds"] == 5


@pytest.mark.asyncio
async def test_wait_status_logs_live_pool_once_per_minute() -> None:
    limiter = CentralizedRateLimiter("org", redis_client=AsyncMock())
    fresh = PoolRedisState(
        limit=184,
        remaining=57,
        reset_at=1_700_000_295.0,
        blocked_until=0,
    )
    decision = AcquireResult(
        decision=RateLimitAcquireDecision.BLOCK,
        wait_seconds=295,
        reason=RateLimitBlockReason.QUOTA_EXHAUSTED,
        remaining=46,
        limit=184,
        reset_at=1_700_000_295.0,
    )
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)))
    try:
        with (
            patch.object(limiter, "_redis_key_for_pool", return_value="pool-key"),
            patch.object(limiter, "_fetch_pool_state", AsyncMock(return_value=fresh)),
            patch(
                "port_ocean.rate_limiting.centralized_rate_limiter.time.time",
                side_effect=[1_000.0, 1_030.0, 1_061.0],
            ),
        ):
            await limiter.log_wait_status(
                "ocean-sandbox",
                SyncTier.LOW,
                decision,
                sleep_remaining_seconds=295,
            )
            await limiter.log_wait_status(
                "ocean-sandbox",
                SyncTier.LOW,
                decision,
                sleep_remaining_seconds=265,
            )
            await limiter.log_wait_status(
                "ocean-sandbox",
                SyncTier.LOW,
                decision,
                sleep_remaining_seconds=234,
            )
    finally:
        logger.remove(sink)

    assert len(messages) == 2
    line = messages[0]
    assert "Centralized rate limiter waiting" in line
    assert "pool=ocean-sandbox" in line
    assert "tier=low" in line
    assert "reason=quota_exhausted" in line
    assert "sleep_remaining_seconds=295" in line
    assert "decision_wait_seconds=295" in line
    assert "remaining=57" in line
    assert "limit=184" in line
    assert "ratio=0.31" in line
    assert "blocked_until=None" in line
    assert "fresh_admission=reserve" in line
    assert "snapshot=fresh" in line
    assert "sleep_remaining_seconds=234" in messages[1]


@pytest.mark.asyncio
async def test_active_limiter_none_when_feature_disabled() -> None:
    with patch(
        "port_ocean.rate_limiting.utils.is_centralized_rate_limiter_enabled",
        return_value=False,
    ):
        assert active_centralized_rate_limiter() is None
