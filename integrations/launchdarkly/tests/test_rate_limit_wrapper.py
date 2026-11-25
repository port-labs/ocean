from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.rate_limiting.models import CentralizedRateLimitState

from client import LaunchDarklyClient
from rate_limit_wrapper import (
    LaunchDarklyRateLimitWrapper,
    centralized_rate_limit_pool,
)
from rate_limiter import LaunchDarklyRateLimiter

NOW = 1_000_000.0
RESET_MS = str(int((NOW + 10) * 1000))


def _wrapper() -> LaunchDarklyRateLimitWrapper:
    return LaunchDarklyRateLimitWrapper(
        LaunchDarklyRateLimiter(),
        pool="app.launchdarkly.com",
        fallback_429_cooldown_seconds=30,
    )


def _response(
    status_code: int = 200,
    *,
    route: tuple[str, str] | None = None,
    global_: tuple[str, str] | None = None,
    reset_ms: str | None = RESET_MS,
    retry_after: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if route is not None:
        headers["x-ratelimit-route-limit"], headers["x-ratelimit-route-remaining"] = (
            route
        )
    if global_ is not None:
        (
            headers["x-ratelimit-global-limit"],
            headers["x-ratelimit-global-remaining"],
        ) = global_
    if reset_ms is not None:
        headers["x-ratelimit-reset"] = reset_ms
    if retry_after is not None:
        headers["retry-after"] = retry_after
    return httpx.Response(status_code, headers=headers)


def _parse(
    wrapper: LaunchDarklyRateLimitWrapper, response: httpx.Response
) -> CentralizedRateLimitState | None:
    with patch("rate_limit_wrapper.time.time", return_value=NOW):
        return wrapper._parse_centralized_state(response, context="/flags")


def test_pool_is_the_launchdarkly_host() -> None:
    assert (
        centralized_rate_limit_pool("https://App.LaunchDarkly.com")
        == "app.launchdarkly.com"
    )
    assert centralized_rate_limit_pool(
        "https://app.launchdarkly.com"
    ) != centralized_rate_limit_pool("https://app.launchdarkly.us")


def test_response_without_rate_limit_headers_is_not_published() -> None:
    assert _parse(_wrapper(), _response(reset_ms=None)) is None


def test_route_limit_wins_over_the_global_limit() -> None:
    state = _parse(_wrapper(), _response(route=("20", "7"), global_=("100", "90")))

    assert state is not None
    assert state.limit == 20
    assert state.remaining == 7
    assert state.blocked_until is None


def test_global_limit_is_used_without_a_route_limit() -> None:
    state = _parse(_wrapper(), _response(global_=("100", "90")))

    assert state is not None
    assert state.limit == 100
    assert state.remaining == 90


def test_reset_is_converted_from_milliseconds() -> None:
    state = _parse(_wrapper(), _response(global_=("100", "90")))

    assert state is not None
    assert state.reset_at == NOW + 10


def test_429_blocks_until_retry_after() -> None:
    wrapper = _wrapper()
    response = _response(429, global_=("100", "0"), retry_after="5")
    state = _parse(wrapper, response)

    assert state is not None
    assert state.remaining == 0
    assert state.limit == 100
    assert state.blocked_until == NOW + 5
    assert wrapper._centralized_is_rate_limited(response) is True


def test_429_without_retry_after_blocks_until_the_window_reset() -> None:
    state = _parse(_wrapper(), _response(429, route=("20", "0")))

    assert state is not None
    assert state.blocked_until == NOW + 10


def test_429_without_any_headers_uses_the_fallback_cooldown() -> None:
    state = _parse(_wrapper(), _response(429, reset_ms=None))

    assert state is not None
    assert state.remaining == 0
    assert state.limit is None
    assert state.blocked_until == NOW + 30


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_host_pool() -> None:
    wrapper = _wrapper()
    with (
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.ocean",
            SimpleNamespace(centralized_rate_limiter=object()),
        ),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.await_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as await_limit,
    ):
        async with wrapper:
            await wrapper.acquire()

    await_limit.assert_awaited_once_with("app.launchdarkly.com")


@pytest.mark.asyncio
async def test_local_mode_feeds_the_launchdarkly_limiter() -> None:
    limiter = LaunchDarklyRateLimiter()
    wrapper = LaunchDarklyRateLimitWrapper(limiter, pool="app.launchdarkly.com")
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.ocean",
        SimpleNamespace(centralized_rate_limiter=None),
    ):
        async with wrapper:
            pass
        await wrapper.record_rate_limit_response(
            _response(route=("20", "1"), reset_ms="9999999999000")
        )

        assert wrapper.is_close_to_rate_limit() is True
        assert wrapper.seconds_until_rate_limit_reset() > 0


def _client_with_response(response: MagicMock) -> LaunchDarklyClient:
    client = LaunchDarklyClient(
        api_token="token", launchdarkly_url="https://app.launchdarkly.com"
    )
    client.http_client.request = AsyncMock(return_value=response)  # type: ignore[method-assign]
    client._rate_limiter.record_rate_limit_response = AsyncMock()  # type: ignore[method-assign]
    return client


@pytest.mark.asyncio
async def test_client_records_non_retryable_responses() -> None:
    response = MagicMock()
    response.json.return_value = {}
    client = _client_with_response(response)

    await client.send_api_request("webhooks/1", method="PATCH", json_data=[])

    client._rate_limiter.record_rate_limit_response.assert_awaited_once_with(  # type: ignore[attr-defined]
        response
    )


@pytest.mark.asyncio
async def test_client_leaves_retryable_responses_to_the_transport() -> None:
    response = MagicMock()
    response.json.return_value = {}
    client = _client_with_response(response)

    await client.send_api_request("flags/project")

    client._rate_limiter.record_rate_limit_response.assert_not_awaited()  # type: ignore[attr-defined]
