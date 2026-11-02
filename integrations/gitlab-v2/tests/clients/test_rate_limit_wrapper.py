from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from gitlab.clients.rate_limiter.limiter import GitLabRateLimiter
from gitlab.clients.rate_limiter.rate_limit_wrapper import (
    MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
    GitLabRateLimitWrapper,
    centralized_rate_limit_pool,
)
from gitlab.clients.rate_limiter.utils import GitLabRateLimiterConfig, RateLimitInfo


def _wrapper() -> GitLabRateLimitWrapper:
    return GitLabRateLimitWrapper(
        GitLabRateLimiter(GitLabRateLimiterConfig()),
        pool="gitlab.example.com-abc",
    )


def _response(
    status_code: int = 200,
    *,
    remaining: str = "1500",
    limit: str = "2000",
    reset: str = "1700000000",
    retry_after: str | None = None,
) -> httpx.Response:
    headers = {
        "ratelimit-remaining": remaining,
        "ratelimit-limit": limit,
        "ratelimit-reset": reset,
    }
    if retry_after is not None:
        headers["retry-after"] = retry_after
    return httpx.Response(status_code, headers=headers)


def test_pool_is_the_gitlab_host() -> None:
    assert (
        centralized_rate_limit_pool("https://gitlab.example.com")
        == "gitlab.example.com"
    )
    assert (
        centralized_rate_limit_pool("https://gitlab.example.com/")
        == "gitlab.example.com"
    )
    assert (
        centralized_rate_limit_pool("https://GitLab.Example.com/api/v4")
        == "gitlab.example.com"
    )


def test_pool_differs_across_hosts() -> None:
    assert centralized_rate_limit_pool(
        "https://gitlab.example.com"
    ) != centralized_rate_limit_pool("https://gitlab.internal")


def test_parse_publishes_vendor_headers() -> None:
    wrapper = _wrapper()
    state = wrapper._parse_centralized_state(
        _response(), context="https://gitlab.example.com/api/v4/projects"
    )

    assert state is not None
    assert state.remaining == 1500
    assert state.limit == 2000
    assert state.reset_at == 1700000000.0
    assert state.blocked_until is None
    assert wrapper._centralized_is_rate_limited(_response()) is False


def test_missing_headers_are_not_published() -> None:
    wrapper = _wrapper()
    response = httpx.Response(200, headers={"x-request-id": "abc"})

    assert wrapper._parse_centralized_state(response, context="projects") is None


def test_429_sets_blocked_until_from_retry_after() -> None:
    wrapper = _wrapper()
    response = _response(HTTPStatus.TOO_MANY_REQUESTS, remaining="0", retry_after="30")

    with patch(
        "gitlab.clients.rate_limiter.rate_limit_wrapper.time.time",
        return_value=1_000_000.0,
    ):
        state = wrapper._parse_centralized_state(response, context="projects")

    assert state is not None
    assert state.blocked_until == 1_000_030.0
    assert wrapper._centralized_is_rate_limited(response) is True


def test_local_action_pause_uses_remaining_threshold() -> None:
    wrapper = _wrapper()
    wrapper._limiter.rate_limit_info = RateLimitInfo(
        remaining=MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS - 1,
        reset_time=1_700_000_100,
        limit=2000,
    )

    assert wrapper._local_is_close_to_rate_limit() is True
    assert wrapper._local_seconds_until_rate_limit_reset() >= 0

    wrapper._limiter.rate_limit_info = RateLimitInfo(
        remaining=MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
        reset_time=1_700_000_100,
        limit=2000,
    )
    assert wrapper._local_is_close_to_rate_limit() is False


@pytest.mark.asyncio
async def test_centralized_acquire_waits_on_the_pool() -> None:
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

    await_limit.assert_awaited_once_with("gitlab.example.com-abc")
