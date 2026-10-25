from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.utils import (
    active_centralized_rate_limiter,
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
async def test_active_limiter_none_when_feature_disabled() -> None:
    with patch(
        "port_ocean.rate_limiting.utils.is_centralized_rate_limiter_enabled",
        return_value=False,
    ):
        assert active_centralized_rate_limiter() is None
