from unittest.mock import AsyncMock, patch

import httpx
import pytest

from clients.rate_limiter import (
    PagerDutyDailyRateLimitExceededError,
    PagerDutyRateLimiter,
)
from clients.rate_limit_wrapper import (
    DAILY_POOL,
    MINUTE_POOL,
    PagerDutyRateLimitWrapper,
)
from port_ocean.rate_limiting.pool_state import PoolRedisState


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
    assert state.reset_at == now + 56
    assert wrapper._centralized_is_rate_limited(response) is True


def test_daily_429_does_not_block_the_minute_pool() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    response = _response(
        429,
        remaining="959",
        reset="40",
        daily_limit="10",
        daily_remaining="-1",
        daily_reset="49015",
    )
    with patch("clients.rate_limit_wrapper.time.time", return_value=now):
        minute = wrapper._parse_centralized_state(response, context="analytics/metrics")
        daily = wrapper._daily_state(response, context="analytics/metrics")

    assert minute is not None
    assert minute.remaining == 959
    assert minute.blocked_until is None
    assert wrapper._centralized_is_rate_limited(response) is False
    assert daily is not None
    assert daily.remaining == -1
    assert daily.limit == 10
    assert daily.reset_at == now + 49015
    assert daily.blocked_until is None


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


def test_rest_response_has_no_daily_state() -> None:
    wrapper = _wrapper()
    assert wrapper._daily_state(_response(), context="services") is None


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_minute_pool() -> None:
    wrapper = _wrapper()
    with (
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.await_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as await_limit,
    ):
        async with wrapper:
            await wrapper.acquire()

    await_limit.assert_awaited_once_with(MINUTE_POOL)


@pytest.mark.asyncio
async def test_daily_publish_does_not_acquire() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    response = _response(
        daily_limit="10",
        daily_remaining="5",
        daily_reset="49015",
    )
    with (
        patch("clients.rate_limit_wrapper.time.time", return_value=now),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "clients.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.record_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as minute_record,
        patch(
            "clients.rate_limit_wrapper.record_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as daily_record,
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.await_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as await_limit,
    ):
        await wrapper.record_rate_limit_response(response, context="analytics/metrics")

    await_limit.assert_not_awaited()
    minute_record.assert_awaited_once()
    minute_call = minute_record.await_args
    assert minute_call is not None
    assert minute_call.args[0] == MINUTE_POOL
    daily_record.assert_awaited_once()
    daily_call = daily_record.await_args
    assert daily_call is not None
    assert daily_call.args[0] == DAILY_POOL
    daily_state = daily_call.args[1]
    assert daily_state.remaining == 5
    assert daily_state.reset_at == now + 49015
    assert daily_state.blocked_until is None
    assert daily_call.kwargs["is_rate_limited"] is False


@pytest.mark.asyncio
async def test_daily_budget_raises_from_redis_without_sleeping() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    snapshot = PoolRedisState(limit=10, remaining=0, reset_at=now + 49015)
    with (
        patch("clients.rate_limit_wrapper.time.time", return_value=now),
        patch(
            "clients.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "clients.rate_limit_wrapper._read_daily_pool",
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.await_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as await_limit,
    ):
        with pytest.raises(PagerDutyDailyRateLimitExceededError):
            await wrapper.check_daily_budget("analytics/metrics/incidents/services")

    await_limit.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_daily_window_does_not_raise() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    snapshot = PoolRedisState(limit=10, remaining=0, reset_at=now - 1)
    with (
        patch("clients.rate_limit_wrapper.time.time", return_value=now),
        patch(
            "clients.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "clients.rate_limit_wrapper._read_daily_pool",
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
    ):
        await wrapper.check_daily_budget("analytics/metrics/incidents/services")


@pytest.mark.asyncio
async def test_daily_budget_ignores_rest_endpoints() -> None:
    wrapper = _wrapper()
    snapshot = PoolRedisState(limit=10, remaining=-1, reset_at=9_999_999_999.0)
    with (
        patch(
            "clients.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "clients.rate_limit_wrapper._read_daily_pool",
            new_callable=AsyncMock,
            return_value=snapshot,
        ) as read_daily,
    ):
        await wrapper.check_daily_budget("services")

    read_daily.assert_not_awaited()
