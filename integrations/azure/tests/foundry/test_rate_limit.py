from unittest.mock import MagicMock

import httpx
import pytest

from azure_integration.foundry.actions.abstract_executor import ArmDeploymentExecutor
from azure_integration.foundry.clients.http.rate_limit import FoundryRateLimiter


def _response(
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {})


def test_observe_requests_pool_and_headroom() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(
        _response(
            headers={
                "x-ratelimit-limit-requests": "100",
                "x-ratelimit-remaining-requests": "50",
                "x-ratelimit-reset-requests": "30",
            }
        )
    )
    assert limiter.is_close_to_rate_limit() is False

    limiter.observe(
        _response(
            headers={
                "x-ratelimit-limit-requests": "100",
                "x-ratelimit-remaining-requests": "5",
                "x-ratelimit-reset-requests": "20",
            }
        )
    )
    assert limiter.is_close_to_rate_limit() is True
    remaining = limiter.seconds_until_rate_limit_reset()
    assert 15 <= remaining <= 20


def test_stale_reset_window_is_treated_as_replenished() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(
        _response(
            headers={
                "x-ratelimit-limit-requests": "100",
                "x-ratelimit-remaining-requests": "1",
                "x-ratelimit-reset-requests": "0",
            }
        )
    )
    assert limiter.is_close_to_rate_limit() is False
    assert limiter.seconds_until_rate_limit_reset() == 0.0


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


@pytest.mark.asyncio
async def test_arm_executor_includes_arm_quota() -> None:
    class _Stub(ArmDeploymentExecutor):
        async def execute(self, run):  # type: ignore[no-untyped-def]
            return None

    executor = _Stub()
    executor.client = MagicMock()
    executor.arm_deployments = MagicMock()
    executor.client.rate_limiter.is_close_to_rate_limit.return_value = False
    executor.arm_deployments.rate_limiter.is_close_to_rate_limit.return_value = True
    executor.client.rate_limiter.seconds_until_rate_limit_reset.return_value = 0.0
    executor.arm_deployments.rate_limiter.seconds_until_rate_limit_reset.return_value = (
        12.0
    )

    run = MagicMock()
    assert await executor.is_close_to_rate_limit(run) is True
    assert await executor.get_remaining_seconds_until_rate_limit(run) == 12.0


def test_parse_duration_suffixes() -> None:
    limiter = FoundryRateLimiter()
    limiter.observe(
        _response(
            headers={
                "x-ratelimit-limit-tokens": "1000",
                "x-ratelimit-remaining-tokens": "50",
                "x-ratelimit-reset-tokens": "5s",
            }
        )
    )
    assert limiter.is_close_to_rate_limit() is True
    assert 4 <= limiter.seconds_until_rate_limit_reset() <= 5
