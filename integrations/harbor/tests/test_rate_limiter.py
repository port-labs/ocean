"""Tests for Harbor rate limiter."""

import asyncio
import time
import pytest
from unittest.mock import MagicMock
import httpx
from harbor.clients.rate_limiter import HarborRateLimiter, RateLimitInfo


# RateLimitInfo Tests
def test_rate_limit_info_seconds_until_reset():
    """Test RateLimitInfo calculates seconds until reset correctly."""
    future_reset = int(time.time()) + 60
    info = RateLimitInfo(remaining=5, reset_time=future_reset, limit=100)

    assert 59 <= info.seconds_until_reset <= 60

    past_reset = int(time.time()) - 10
    info_past = RateLimitInfo(remaining=0, reset_time=past_reset, limit=100)

    assert info_past.seconds_until_reset == 0


def test_rate_limit_info_utilization_percentage():
    """Test RateLimitInfo calculates utilization correctly."""
    info = RateLimitInfo(remaining=25, reset_time=0, limit=100)
    assert info.utilization_percentage == 75.0

    info_full = RateLimitInfo(remaining=0, reset_time=0, limit=100)
    assert info_full.utilization_percentage == 100.0

    info_empty = RateLimitInfo(remaining=100, reset_time=0, limit=100)
    assert info_empty.utilization_percentage == 0.0


def test_rate_limit_info_zero_limit():
    """Test RateLimitInfo handles zero limit gracefully."""
    info = RateLimitInfo(remaining=0, reset_time=0, limit=0)
    assert info.utilization_percentage == 0


# HarborRateLimiter Tests
def test_rate_limiter_initialization():
    """Test HarborRateLimiter initializes correctly."""
    limiter = HarborRateLimiter(max_concurrent=5)

    assert limiter.max_concurrent == 5
    assert limiter.rate_limit_info is None


def test_rate_limiter_default_initialization():
    """Test HarborRateLimiter uses default max_concurrent."""
    limiter = HarborRateLimiter()

    assert limiter.max_concurrent == 10


def test_rate_limiter_update_rate_limits():
    """Test HarborRateLimiter updates rate limits from headers."""
    limiter = HarborRateLimiter()

    headers = httpx.Headers(
        {
            "x-ratelimit-limit": "100",
            "x-ratelimit-remaining": "50",
            "x-ratelimit-reset": str(int(time.time()) + 60),
        }
    )

    info = limiter.update_rate_limits(headers, "/projects")

    assert info is not None
    assert info.limit == 100
    assert info.remaining == 50
    assert limiter.rate_limit_info == info


def test_rate_limiter_update_rate_limits_missing_headers():
    """Test HarborRateLimiter handles missing headers gracefully."""
    limiter = HarborRateLimiter()

    headers = httpx.Headers({})

    info = limiter.update_rate_limits(headers, "/projects")

    assert info is None
    assert limiter.rate_limit_info is None


def test_rate_limiter_update_rate_limits_partial_headers():
    """Test HarborRateLimiter handles partial headers gracefully."""
    limiter = HarborRateLimiter()

    # Missing x-ratelimit-reset
    headers = httpx.Headers(
        {
            "x-ratelimit-limit": "100",
            "x-ratelimit-remaining": "50",
        }
    )

    info = limiter.update_rate_limits(headers, "/projects")

    assert info is None


def test_rate_limiter_update_rate_limits_invalid_values():
    """Test HarborRateLimiter handles invalid header values gracefully."""
    limiter = HarborRateLimiter()

    headers = httpx.Headers(
        {
            "x-ratelimit-limit": "invalid",
            "x-ratelimit-remaining": "50",
            "x-ratelimit-reset": str(int(time.time()) + 60),
        }
    )

    info = limiter.update_rate_limits(headers, "/projects")

    assert info is None


def test_rate_limiter_is_rate_limit_response():
    """Test HarborRateLimiter detects rate limit responses."""
    limiter = HarborRateLimiter()

    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    assert limiter.is_rate_limit_response(mock_response_429) is True

    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    assert limiter.is_rate_limit_response(mock_response_200) is False

    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    assert limiter.is_rate_limit_response(mock_response_500) is False


def test_rate_limiter_log_rate_limit_status_with_info():
    """Test log_rate_limit_status logs when rate limit info is available."""
    limiter = HarborRateLimiter()
    limiter.rate_limit_info = RateLimitInfo(remaining=50, reset_time=int(time.time()) + 60, limit=100)

    # Should not raise an error
    limiter.log_rate_limit_status()


def test_rate_limiter_log_rate_limit_status_no_info():
    """Test log_rate_limit_status logs when no rate limit info."""
    limiter = HarborRateLimiter()

    # Should not raise an error
    limiter.log_rate_limit_status()


# Async Context Manager Tests
@pytest.mark.asyncio
async def test_rate_limiter_context_manager():
    """Test HarborRateLimiter works as async context manager."""
    limiter = HarborRateLimiter(max_concurrent=2)

    async with limiter:
        pass

    assert limiter._semaphore._value == 2


@pytest.mark.asyncio
async def test_rate_limiter_concurrency_control():
    """Test HarborRateLimiter limits concurrent requests."""
    limiter = HarborRateLimiter(max_concurrent=2)
    active_count = 0
    max_active = 0

    async def task():
        nonlocal active_count, max_active
        async with limiter:
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.01)
            active_count -= 1

    await asyncio.gather(*[task() for _ in range(5)])

    assert max_active <= 2


@pytest.mark.asyncio
async def test_rate_limiter_releases_on_exception():
    """Test HarborRateLimiter releases semaphore even when exception occurs."""
    limiter = HarborRateLimiter(max_concurrent=1)

    try:
        async with limiter:
            raise ValueError("Test error")
    except ValueError:
        pass

    # Semaphore should be released
    assert limiter._semaphore._value == 1
