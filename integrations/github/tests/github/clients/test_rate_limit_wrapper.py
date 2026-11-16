import time

import pytest

from github.clients.rate_limiter.limiter import GitHubRateLimiter
from github.clients.rate_limiter.rate_limit_wrapper import (
    MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
    GitHubRateLimitWrapper,
)
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig, RateLimitInfo


@pytest.fixture
def limiter() -> GitHubRateLimiter:
    return GitHubRateLimiter(GitHubRateLimiterConfig(api_type="rest", max_concurrent=5))


@pytest.fixture
def wrapper(limiter: GitHubRateLimiter) -> GitHubRateLimitWrapper:
    # redis_enabled=False keeps the check on the local limiter path
    return GitHubRateLimitWrapper(limiter, "rest", "rest", redis_enabled=False)


def _info(remaining: int, reset_in_seconds: int) -> RateLimitInfo:
    return RateLimitInfo(
        remaining=remaining,
        reset_time=int(time.time()) + reset_in_seconds,
        limit=5000,
    )


class TestRateLimitInfoIsExpired:
    def test_not_expired_before_reset(self) -> None:
        assert _info(remaining=0, reset_in_seconds=60).is_expired is False

    def test_expired_at_reset_time(self) -> None:
        assert _info(remaining=0, reset_in_seconds=0).is_expired is True

    def test_expired_after_reset_time(self) -> None:
        assert _info(remaining=0, reset_in_seconds=-30).is_expired is True


class TestWrapperIsCloseToRateLimit:
    def test_not_close_without_info(self, wrapper: GitHubRateLimitWrapper) -> None:
        assert wrapper.is_close_to_rate_limit() is False

    def test_close_when_low_remaining_and_window_active(
        self, limiter: GitHubRateLimiter, wrapper: GitHubRateLimitWrapper
    ) -> None:
        limiter.rate_limit_info = _info(
            remaining=MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS - 1, reset_in_seconds=60
        )
        assert wrapper.is_close_to_rate_limit() is True

    def test_not_close_when_enough_remaining(
        self, limiter: GitHubRateLimiter, wrapper: GitHubRateLimitWrapper
    ) -> None:
        limiter.rate_limit_info = _info(
            remaining=MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS, reset_in_seconds=60
        )
        assert wrapper.is_close_to_rate_limit() is False

    def test_not_close_when_window_has_reset_despite_stale_remaining(
        self, limiter: GitHubRateLimiter, wrapper: GitHubRateLimitWrapper
    ) -> None:
        # Regression: the action pre-check sends no requests, so `remaining`
        # stays at 0 after the reset and used to block runs forever.
        limiter.rate_limit_info = _info(remaining=0, reset_in_seconds=-1)
        assert wrapper.is_close_to_rate_limit() is False
