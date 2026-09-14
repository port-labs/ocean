import time
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.core.models import IntegrationRun

from actions.abstract_pagerduty_executor import AbstractPagerDutyExecutor
from clients.rate_limiter import RateLimitInfo


class _TestExecutor(AbstractPagerDutyExecutor):
    ACTION_NAME = "test_action"

    async def execute(self, run: IntegrationRun) -> None:
        pass


def _build_executor(
    rate_limit_info: RateLimitInfo | None,
) -> _TestExecutor:
    client_mock = MagicMock()
    client_mock.get_rate_limit_status.return_value = rate_limit_info
    with patch.object(AbstractPagerDutyExecutor, "__init__", lambda self: None):
        executor = _TestExecutor()
    executor.client = client_mock
    return executor


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_when_remaining_is_low() -> None:
    executor = _build_executor(
        RateLimitInfo.with_seconds_until_reset(
            limit=960, remaining=10, seconds_until_reset=30
        )
    )

    assert await executor.is_close_to_rate_limit(MagicMock()) is True


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_when_remaining_is_high() -> None:
    executor = _build_executor(
        RateLimitInfo.with_seconds_until_reset(
            limit=960, remaining=100, seconds_until_reset=30
        )
    )

    assert await executor.is_close_to_rate_limit(MagicMock()) is False


@pytest.mark.asyncio
async def test_is_close_to_rate_limit_false_once_reset_window_has_passed() -> None:
    executor = _build_executor(
        RateLimitInfo(
            limit=960,
            remaining=10,
            reset_at=int(time.time()) - 5,
        )
    )

    assert await executor.is_close_to_rate_limit(MagicMock()) is False


@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_returns_zero_when_not_close() -> (
    None
):
    executor = _build_executor(
        RateLimitInfo.with_seconds_until_reset(
            limit=960, remaining=100, seconds_until_reset=30
        )
    )

    assert await executor.get_remaining_seconds_until_rate_limit(MagicMock()) == 0.0


@pytest.mark.asyncio
async def test_get_remaining_seconds_until_rate_limit_returns_reset_countdown() -> None:
    executor = _build_executor(
        RateLimitInfo.with_seconds_until_reset(
            limit=960, remaining=10, seconds_until_reset=25
        )
    )

    remaining = await executor.get_remaining_seconds_until_rate_limit(MagicMock())

    assert 24 <= remaining <= 25
