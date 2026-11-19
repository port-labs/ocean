from unittest.mock import MagicMock

import httpx
import pytest

from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.actions.arm_deployment_executor import (
    ArmDeploymentExecutor,
)
from azure_integration.foundry.clients.http.rate_limit import FoundryRateLimiter


def _response(
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {})


def test_429_sets_hard_block_from_retry_after_ms() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(_response(status_code=429, headers={"retry-after-ms": "2500"}))
    assert limiter.is_close_to_rate_limit() is True
    remaining = limiter.seconds_until_rate_limit_reset()
    assert 2.0 <= remaining <= 2.5


def test_arm_remaining_floor() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(
        _response(headers={"x-ms-ratelimit-remaining-subscription-writes": "1"})
    )
    assert limiter.is_close_to_rate_limit() is True
    assert limiter.seconds_until_rate_limit_reset() > 0


def test_arm_remaining_above_floor_clears_block() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(
        _response(headers={"x-ms-ratelimit-remaining-subscription-writes": "1"})
    )
    limiter.observe(
        _response(headers={"x-ms-ratelimit-remaining-subscription-writes": "50"})
    )
    assert limiter.is_close_to_rate_limit() is False


@pytest.mark.asyncio
async def test_agent_executor_honors_hard_429() -> None:
    class _Stub(AbstractFoundryExecutor):
        async def execute(self, run):  # type: ignore[no-untyped-def]
            return None

    executor = _Stub()
    executor.client = MagicMock()
    executor.client.rate_limiter.is_close_to_rate_limit.return_value = False
    executor.client.rate_limiter.seconds_until_rate_limit_reset.return_value = 0.0
    run = MagicMock()
    assert await executor.is_close_to_rate_limit(run) is False
    assert await executor.get_remaining_seconds_until_rate_limit(run) == 0.0

    executor.client.rate_limiter.is_close_to_rate_limit.return_value = True
    executor.client.rate_limiter.seconds_until_rate_limit_reset.return_value = 3.5
    assert await executor.is_close_to_rate_limit(run) is True
    assert await executor.get_remaining_seconds_until_rate_limit(run) == 3.5


@pytest.mark.asyncio
async def test_arm_executor_includes_arm_quota() -> None:
    class _Stub(ArmDeploymentExecutor):
        async def execute(self, run):  # type: ignore[no-untyped-def]
            return None

    executor = _Stub()
    executor.client = MagicMock()
    executor.foundry_arm = MagicMock()
    executor.client.rate_limiter.is_close_to_rate_limit.return_value = False
    executor.client.rate_limiter.seconds_until_rate_limit_reset.return_value = 0.0
    executor.foundry_arm.rate_limiter.is_close_to_rate_limit.return_value = True
    executor.foundry_arm.rate_limiter.seconds_until_rate_limit_reset.return_value = 12.0

    run = MagicMock()
    assert await executor.is_close_to_rate_limit(run) is True
    assert await executor.get_remaining_seconds_until_rate_limit(run) == 12.0


def test_hard_block_clears_on_success() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(_response(status_code=429, headers={"retry-after-ms": "4000"}))
    assert 3.0 <= limiter.hard_block_seconds() <= 4.0
    limiter.observe(_response())
    assert limiter.hard_block_seconds() == 0.0
    assert limiter.is_close_to_rate_limit() is False


def test_retry_after_duration_suffix() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(_response(status_code=429, headers={"Retry-After": "5s"}))
    assert limiter.is_close_to_rate_limit() is True
    assert 4 <= limiter.seconds_until_rate_limit_reset() <= 5
