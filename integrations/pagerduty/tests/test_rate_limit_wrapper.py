from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from clients.rate_limiter import (
    PagerDutyDailyRateLimitExceededError,
    PagerDutyRateLimiter,
)
from clients.rate_limit_wrapper import (
    MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
    MINUTE_POOL,
    PagerDutyRateLimitWrapper,
)


def _wrapper() -> PagerDutyRateLimitWrapper:
    return PagerDutyRateLimitWrapper(PagerDutyRateLimiter(), pool=MINUTE_POOL)


def _response(
    status_code: int = 200,
    *,
    limit: str | None = "960",
    remaining: str | None = "900",
    reset: str | None = "30",
    daily_limit: str | None = None,
    daily_remaining: str | None = None,
    daily_reset: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if limit is not None:
        headers["ratelimit-limit"] = limit
    if remaining is not None:
        headers["ratelimit-remaining"] = remaining
    if reset is not None:
        headers["ratelimit-reset"] = reset
    if daily_limit is not None:
        headers["daily-ratelimit-limit"] = daily_limit
    if daily_remaining is not None:
        headers["daily-ratelimit-remaining"] = daily_remaining
    if daily_reset is not None:
        headers["daily-ratelimit-reset"] = daily_reset
    return httpx.Response(status_code, headers=headers)


def _redis_on() -> SimpleNamespace:
    return SimpleNamespace(centralized_rate_limiter=object())


def test_minute_reset_header_becomes_an_absolute_epoch() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    with patch("clients.rate_limit_wrapper.time.time", return_value=now):
        state = wrapper._parse_centralized_state(
            _response(reset="56"), context="services"
        )

    assert state is not None
    assert state.remaining == 900
    assert state.limit == 960
    assert state.reset_at == now + 56
    assert state.blocked_until is None


def test_missing_minute_headers_are_not_published() -> None:
    wrapper = _wrapper()
    response = httpx.Response(200, headers={"x-request-id": "abc"})
    assert wrapper._parse_centralized_state(response, context="services") is None


def test_minute_429_sets_blocked_until_from_reset_seconds() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    response = _response(429, remaining="0", reset="56")
    with patch("clients.rate_limit_wrapper.time.time", return_value=now):
        state = wrapper._parse_centralized_state(response, context="services")

    assert state is not None
    assert state.remaining == 0
    assert state.blocked_until == now + 56
    assert wrapper._centralized_is_rate_limited(response) is True


def test_daily_429_does_not_block_the_minute_pool() -> None:
    wrapper = _wrapper()
    response = _response(
        429,
        remaining="959",
        reset="40",
        daily_limit="10",
        daily_remaining="-1",
        daily_reset="49015",
    )

    state = wrapper._parse_centralized_state(response, context="analytics/metrics")

    assert state is not None
    assert state.remaining == 959
    assert state.blocked_until is None
    assert wrapper._centralized_is_rate_limited(response) is False


def test_minute_and_daily_exhausted_still_blocks_the_minute_pool() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    response = _response(
        429,
        remaining="0",
        reset="20",
        daily_limit="10",
        daily_remaining="0",
        daily_reset="1000",
    )
    with patch("clients.rate_limit_wrapper.time.time", return_value=now):
        state = wrapper._parse_centralized_state(response, context="analytics/metrics")

    assert state is not None
    assert state.blocked_until == now + 20
    assert wrapper._centralized_is_rate_limited(response) is True


@pytest.mark.asyncio
async def test_redis_publishes_only_the_minute_pool() -> None:
    wrapper = _wrapper()
    response = _response(daily_limit="10", daily_remaining="3", daily_reset="1000")
    with (
        patch("port_ocean.rate_limiting.rate_limit_wrapper.ocean", _redis_on()),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.record_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as record_limit,
    ):
        await wrapper.record_rate_limit_response(response, context="analytics/x")

    record_limit.assert_awaited_once()
    assert record_limit.await_args is not None
    assert record_limit.await_args.args[0] == MINUTE_POOL


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_minute_pool() -> None:
    wrapper = _wrapper()
    with (
        patch("port_ocean.rate_limiting.rate_limit_wrapper.ocean", _redis_on()),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.await_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as await_limit,
    ):
        async with wrapper:
            await wrapper.acquire()

    await_limit.assert_awaited_once_with(MINUTE_POOL)


def test_daily_budget_raises_from_the_local_snapshot() -> None:
    wrapper = _wrapper()
    wrapper.update_rate_limits(
        _response(daily_limit="10", daily_remaining="0", daily_reset="1000").headers,
        "analytics/metrics/incidents/services",
    )

    with pytest.raises(PagerDutyDailyRateLimitExceededError):
        wrapper.check_daily_budget("analytics/metrics/incidents/services")
    wrapper.check_daily_budget("services")


def test_local_action_pause_uses_remaining_threshold() -> None:
    wrapper = _wrapper()
    wrapper.update_rate_limits(
        _response(remaining=str(MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS - 1)).headers,
        "incidents",
    )

    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.ocean",
        SimpleNamespace(centralized_rate_limiter=None),
    ):
        assert wrapper.is_close_to_rate_limit() is True
        assert wrapper.seconds_until_rate_limit_reset() > 0

    with patch("port_ocean.rate_limiting.rate_limit_wrapper.ocean", _redis_on()):
        assert wrapper.is_close_to_rate_limit() is False
        assert wrapper.seconds_until_rate_limit_reset() == 0.0
