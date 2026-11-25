from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from port_ocean.rate_limiting.models import CentralizedRateLimitState

from clients.rate_limit_wrapper import (
    SentryRateLimitWrapper,
    centralized_rate_limit_pool,
)
from clients.rate_limiter import SentryRateLimiter

NOW = 1_000_000.0
RESET = str(int(NOW + 5))
POOL = "sentry.io:my-org"


def _wrapper() -> SentryRateLimitWrapper:
    return SentryRateLimitWrapper(
        SentryRateLimiter(), pool=POOL, fallback_429_cooldown_seconds=30
    )


def _response(
    status_code: int = 200,
    *,
    limit: str | None = "40",
    remaining: str | None = "12",
    reset: str | None = RESET,
    retry_after: str | None = None,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if limit is not None:
        headers["x-sentry-rate-limit-limit"] = limit
    if remaining is not None:
        headers["x-sentry-rate-limit-remaining"] = remaining
    if reset is not None:
        headers["x-sentry-rate-limit-reset"] = reset
    if retry_after is not None:
        headers["retry-after"] = retry_after
    return httpx.Response(status_code, headers=headers)


def _parse(
    wrapper: SentryRateLimitWrapper, response: httpx.Response
) -> CentralizedRateLimitState | None:
    with patch("clients.rate_limit_wrapper.time.time", return_value=NOW):
        return wrapper._parse_centralized_state(response, context="/issues")


def test_pool_is_the_sentry_host_and_organization() -> None:
    assert centralized_rate_limit_pool("https://Sentry.io", "My-Org") == POOL
    assert centralized_rate_limit_pool(
        "https://sentry.io", "my-org"
    ) != centralized_rate_limit_pool("https://sentry.example.com", "my-org")


def test_response_without_rate_limit_headers_is_not_published() -> None:
    response = _response(limit=None, remaining=None, reset=None)
    assert _parse(_wrapper(), response) is None


def test_normal_response_publishes_the_real_quota() -> None:
    state = _parse(_wrapper(), _response())

    assert state is not None
    assert state.limit == 40
    assert state.remaining == 12
    assert state.reset_at == NOW + 5
    assert state.blocked_until is None


def test_429_blocks_until_retry_after() -> None:
    wrapper = _wrapper()
    response = _response(429, remaining="0", retry_after="3")
    state = _parse(wrapper, response)

    assert state is not None
    assert state.remaining == 0
    assert state.limit == 40
    assert state.blocked_until == NOW + 3
    assert wrapper._centralized_is_rate_limited(response) is True


def test_429_without_retry_after_blocks_until_the_window_reset() -> None:
    state = _parse(_wrapper(), _response(429, remaining="0"))

    assert state is not None
    assert state.blocked_until == NOW + 5


def test_429_without_any_headers_uses_the_fallback_cooldown() -> None:
    response = _response(429, limit=None, remaining=None, reset=None)
    state = _parse(_wrapper(), response)

    assert state is not None
    assert state.remaining == 0
    assert state.limit is None
    assert state.blocked_until == NOW + 30


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_organization_pool() -> None:
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

    await_limit.assert_awaited_once_with(POOL)


@pytest.mark.asyncio
async def test_local_mode_feeds_the_sentry_limiter() -> None:
    wrapper = SentryRateLimitWrapper(SentryRateLimiter(), pool=POOL)
    async with wrapper:
        pass
    await wrapper.record_rate_limit_response(
        _response(remaining="1", reset="9999999999")
    )

    assert wrapper.is_close_to_rate_limit() is True
    assert wrapper.seconds_until_rate_limit_reset() > 0
