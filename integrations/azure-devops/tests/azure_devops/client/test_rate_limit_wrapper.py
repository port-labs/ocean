from unittest.mock import AsyncMock, patch

import httpx

from azure_devops.client.rate_limiter import AzureDevOpsRateLimiter
from azure_devops.client.rate_limit_wrapper import (
    AzureDevOpsRateLimitWrapper,
    centralized_rate_limit_pool,
)


def _wrapper() -> AzureDevOpsRateLimitWrapper:
    return AzureDevOpsRateLimitWrapper(AzureDevOpsRateLimiter(), pool="ocean-sandbox")


def test_headers_become_redis_state() -> None:
    response = httpx.Response(
        200,
        headers={
            "x-ratelimit-limit": "200",
            "x-ratelimit-remaining": "50",
            "x-ratelimit-reset": "1700000000",
        },
    )

    state = _wrapper()._parse_centralized_state(response, "request")

    assert state is not None
    assert state.limit == 200
    assert state.remaining == 50
    assert state.reset_at == 1700000000.0
    assert state.blocked_until is None
    assert _wrapper()._centralized_is_rate_limited(response) is False


def test_missing_headers_publish_nothing() -> None:
    response = httpx.Response(200, headers={})

    assert _wrapper()._parse_centralized_state(response, "request") is None


def test_retry_after_blocks_only_on_429() -> None:
    throttled = httpx.Response(
        429,
        headers={
            "x-ratelimit-limit": "200",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1700000360",
            "retry-after": "12",
        },
    )
    ok = httpx.Response(200, headers={"retry-after": "12"})
    wrapper = _wrapper()

    with patch("azure_devops.client.rate_limit_wrapper.time.time", return_value=1000.0):
        state = wrapper._parse_centralized_state(throttled, "request")

    assert state is not None
    assert state.blocked_until == 1012.0
    assert state.remaining == 0
    assert wrapper._centralized_is_rate_limited(throttled) is True
    assert wrapper._parse_centralized_state(ok, "request") is None


def test_unparseable_retry_after_warns_and_uses_ado_window() -> None:
    response = httpx.Response(429, headers={"retry-after": "soon"})
    wrapper = _wrapper()

    with (
        patch("azure_devops.client.rate_limit_wrapper.time.time", return_value=1000.0),
        patch("azure_devops.client.rate_limit_wrapper.logger.warning") as warning,
    ):
        state = wrapper._parse_centralized_state(response, "request")

    assert state is not None
    assert state.blocked_until == 1360.0
    warning.assert_called_once()


def test_429_without_retry_after_uses_ado_window() -> None:
    response = httpx.Response(429, headers={})
    wrapper = _wrapper()

    with patch("azure_devops.client.rate_limit_wrapper.time.time", return_value=1000.0):
        state = wrapper._parse_centralized_state(response, "request")

    assert state is not None
    assert state.blocked_until == 1360.0
    assert state.limit is None


async def test_redis_acquire_waits_out_local_throttle_first() -> None:
    wrapper = _wrapper()
    wrapper._limiter._throttle_until = 1300.0

    with (
        patch.object(wrapper, "_redis_admission_enabled", return_value=True),
        patch(
            "azure_devops.client.rate_limit_wrapper.RateLimitWrapper.acquire",
            new_callable=AsyncMock,
        ) as redis_acquire,
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch(
            "azure_devops.client.rate_limiter.time.time",
            return_value=1000.0,
        ),
    ):
        await wrapper.acquire()

    sleep.assert_awaited_once_with(300.0)
    redis_acquire.assert_awaited_once()
    assert wrapper._limiter._throttle_until is None


async def test_local_acquire_leaves_timeout_cooldown_for_entry() -> None:
    wrapper = _wrapper()
    wrapper._limiter._throttle_until = 1300.0

    with (
        patch.object(wrapper, "_redis_admission_enabled", return_value=False),
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        await wrapper.acquire()

    sleep.assert_not_awaited()
    assert wrapper._limiter._throttle_until == 1300.0


def test_pool_is_the_azure_organization_name() -> None:
    assert (
        centralized_rate_limit_pool("https://dev.azure.com/ocean-sandbox")
        == "ocean-sandbox"
    )
    assert (
        centralized_rate_limit_pool("https://vsrm.dev.azure.com/ocean-sandbox")
        == "ocean-sandbox"
    )
    assert (
        centralized_rate_limit_pool("https://advsec.dev.azure.com/ocean-sandbox")
        == "ocean-sandbox"
    )
    assert (
        centralized_rate_limit_pool("https://ocean-sandbox.visualstudio.com")
        == "ocean-sandbox"
    )
    assert centralized_rate_limit_pool("https://dev.azure.com/oceane2e") == "oceane2e"
