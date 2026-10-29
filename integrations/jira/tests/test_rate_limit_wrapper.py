from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from jira.rate_limiter import (
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    JiraRateLimiter,
)
from jira.rate_limit_wrapper import JiraRateLimitWrapper, centralized_rate_limit_pool


def _wrapper() -> JiraRateLimitWrapper:
    return JiraRateLimitWrapper(JiraRateLimiter(), pool="example.atlassian.net")


def _response(
    status_code: int = 200,
    *,
    limit: str | None = "100",
    remaining: str | None = "40",
    reset: str | None = None,
    retry_after: str | None = None,
    near_limit: bool = False,
) -> httpx.Response:
    headers: dict[str, str] = {}
    if limit is not None:
        headers["x-ratelimit-limit"] = limit
    if remaining is not None:
        headers["x-ratelimit-remaining"] = remaining
    if reset is not None:
        headers["x-ratelimit-reset"] = reset
    if retry_after is not None:
        headers["retry-after"] = retry_after
    if near_limit:
        headers["x-ratelimit-nearlimit"] = "true"
    return httpx.Response(status_code, headers=headers)


def test_pool_is_the_jira_host() -> None:
    assert (
        centralized_rate_limit_pool("https://example.atlassian.net")
        == "example.atlassian.net"
    )
    assert (
        centralized_rate_limit_pool("https://Example.Atlassian.net/rest/api/3")
        == "example.atlassian.net"
    )


def test_pool_differs_across_sites() -> None:
    assert centralized_rate_limit_pool(
        "https://one.atlassian.net"
    ) != centralized_rate_limit_pool("https://two.atlassian.net")


def test_200_without_reset_uses_a_short_window() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    with patch("jira.rate_limit_wrapper.time.time", return_value=now):
        state = wrapper._parse_centralized_state(_response(), context="/issue")

    assert state is not None
    assert state.remaining == 40
    assert state.limit == 100
    assert state.reset_at == now + DEFAULT_RATE_LIMIT_WINDOW_SECONDS
    assert state.blocked_until is None


def test_200_keeps_a_reset_learned_from_an_earlier_response() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    explicit = "2099-01-01T00:00:00Z"
    expected = datetime.fromisoformat("2099-01-01T00:00:00+00:00").timestamp()
    with patch("jira.rate_limit_wrapper.time.time", return_value=now):
        first = wrapper._parse_centralized_state(
            _response(reset=explicit), context="/issue"
        )
        second = wrapper._parse_centralized_state(_response(), context="/issue")

    assert first is not None and second is not None
    assert first.reset_at == expected
    assert second.reset_at == expected
    assert second.remaining == 40


def test_429_sets_blocked_until_from_retry_after() -> None:
    wrapper = _wrapper()
    now = 1_000_000.0
    response = _response(429, remaining="0", retry_after="30")
    with patch("jira.rate_limit_wrapper.time.time", return_value=now):
        state = wrapper._parse_centralized_state(response, context="/issue")

    assert state is not None
    assert state.remaining == 0
    assert state.blocked_until == now + 30
    assert state.reset_at == now + 30
    assert wrapper._centralized_is_rate_limited(response) is True


def test_missing_quota_headers_are_not_published() -> None:
    wrapper = _wrapper()
    response = httpx.Response(200, headers={"x-request-id": "abc"})
    assert wrapper._parse_centralized_state(response, context="/issue") is None


def test_near_limit_publishes_empty_remaining() -> None:
    wrapper = _wrapper()
    state = wrapper._parse_centralized_state(
        _response(remaining="80", near_limit=True), context="/issue"
    )
    assert state is not None
    assert state.remaining == 0


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_site_pool() -> None:
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

    await_limit.assert_awaited_once_with("example.atlassian.net")


def test_explicit_reset_is_absolute() -> None:
    wrapper = _wrapper()
    raw = "2099-06-01T00:00:00+00:00"
    expected = datetime.fromisoformat(raw).timestamp()
    state = wrapper._parse_centralized_state(_response(reset=raw), context="/issue")
    assert state is not None
    assert state.reset_at == expected
