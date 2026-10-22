from unittest.mock import patch

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


def test_429_without_retry_after_uses_ado_window() -> None:
    response = httpx.Response(429, headers={})
    wrapper = _wrapper()

    with patch("azure_devops.client.rate_limit_wrapper.time.time", return_value=1000.0):
        state = wrapper._parse_centralized_state(response, "request")

    assert state is not None
    assert state.blocked_until == 1360.0
    assert state.limit is None


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
