from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from port_ocean.rate_limiting.models import CentralizedRateLimitState

from rate_limit_wrapper import ServiceNowRateLimitWrapper, centralized_rate_limit_pool
from rate_limiter import ServiceNowRateLimiter

NOW = 1_000_000.0


def _wrapper() -> ServiceNowRateLimitWrapper:
    return ServiceNowRateLimitWrapper(
        ServiceNowRateLimiter(),
        pool="example.service-now.com",
        fallback_429_cooldown_seconds=120,
    )


def _response(
    status_code: int = 200,
    *,
    limit: str | None = "1000",
    reset: str | None = str(NOW + 3600),
    retry_after: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if limit is not None:
        headers["x-ratelimit-limit"] = limit
    if reset is not None:
        headers["x-ratelimit-reset"] = reset
    if retry_after is not None:
        headers["retry-after"] = retry_after
    return httpx.Response(status_code, headers=headers)


def _parse(
    wrapper: ServiceNowRateLimitWrapper, response: httpx.Response
) -> CentralizedRateLimitState | None:
    with patch("rate_limit_wrapper.time.time", return_value=NOW):
        return wrapper._parse_centralized_state(response, context="/table")


def test_pool_is_the_instance_host() -> None:
    assert (
        centralized_rate_limit_pool("https://Example.service-now.com/api/now")
        == "example.service-now.com"
    )
    assert centralized_rate_limit_pool(
        "https://one.service-now.com"
    ) != centralized_rate_limit_pool("https://two.service-now.com")


def test_response_without_rate_limit_rule_is_not_published() -> None:
    wrapper = _wrapper()
    assert _parse(wrapper, _response(limit=None, reset=None)) is None


def test_first_response_of_a_window_publishes_the_full_quota() -> None:
    state = _parse(_wrapper(), _response())

    assert state is not None
    assert state.limit == 1000
    assert state.remaining == 999
    assert state.reset_at == NOW + 3600
    assert state.blocked_until is None


def test_later_responses_in_the_same_window_leave_remaining_to_redis() -> None:
    wrapper = _wrapper()
    _parse(wrapper, _response())
    state = _parse(wrapper, _response())

    assert state is not None
    assert state.remaining is None
    assert state.limit == 1000
    assert state.reset_at == NOW + 3600


def test_a_new_reset_opens_a_new_window() -> None:
    wrapper = _wrapper()
    _parse(wrapper, _response())
    state = _parse(wrapper, _response(reset=str(NOW + 7200)))

    assert state is not None
    assert state.remaining == 999
    assert state.reset_at == NOW + 7200


def test_past_reset_does_not_reset_the_quota() -> None:
    state = _parse(_wrapper(), _response(reset=str(NOW - 1)))

    assert state is not None
    assert state.remaining is None


def test_429_blocks_until_retry_after() -> None:
    wrapper = _wrapper()
    response = _response(429, retry_after="300")
    state = _parse(wrapper, response)

    assert state is not None
    assert state.remaining == 0
    assert state.blocked_until == NOW + 300
    assert wrapper._centralized_is_rate_limited(response) is True


def test_429_without_retry_after_blocks_until_the_window_reset() -> None:
    state = _parse(_wrapper(), _response(429))

    assert state is not None
    assert state.blocked_until == NOW + 3600


def test_429_without_any_headers_uses_the_fallback_cooldown() -> None:
    wrapper = _wrapper()
    _parse(wrapper, _response())
    state = _parse(wrapper, _response(429, limit=None, reset=None))

    assert state is not None
    assert state.limit == 1000
    assert state.remaining == 0
    assert state.blocked_until == NOW + 120


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_instance_pool() -> None:
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

    await_limit.assert_awaited_once_with("example.service-now.com")


@pytest.mark.asyncio
async def test_local_mode_feeds_the_servicenow_limiter() -> None:
    limiter = ServiceNowRateLimiter()
    wrapper = ServiceNowRateLimitWrapper(limiter, pool="example.service-now.com")
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.ocean",
        SimpleNamespace(centralized_rate_limiter=None),
    ):
        async with wrapper:
            pass
        await wrapper.record_rate_limit_response(
            _response(limit="1", reset=str(9_999_999_999))
        )

        assert wrapper.is_close_to_rate_limit() is True
        assert wrapper.seconds_until_rate_limit_reset() > 0
