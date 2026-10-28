from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
    RateLimitBlockReason,
    SyncTier,
)
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
async def test_await_centralized_rate_limit_sleeps_for_the_block() -> None:
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

    sleep.assert_awaited_once_with(125)
    assert mock_limiter.acquire.await_count == 2


@pytest.mark.asyncio
async def test_active_limiter_none_when_ocean_is_not_initialized() -> None:
    with patch(
        "port_ocean.rate_limiting.utils.ocean",
        SimpleNamespace(initialized=False),
    ):
        assert active_centralized_rate_limiter() is None
