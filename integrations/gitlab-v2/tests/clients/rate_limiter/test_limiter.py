import asyncio
import time
from typing import Generator
from unittest.mock import Mock, patch

import httpx
import pytest

from gitlab.clients.rate_limiter.limiter import GitLabRateLimiter
from gitlab.clients.rate_limiter.utils import GitLabRateLimiterConfig, RateLimitInfo


@pytest.fixture
def config() -> GitLabRateLimiterConfig:
    """Create a rate limiter config with low concurrency for testing."""
    return GitLabRateLimiterConfig(max_concurrent=5)


@pytest.fixture
def rate_limiter(config: GitLabRateLimiterConfig) -> GitLabRateLimiter:
    """Create a fresh rate limiter for each test."""
    return GitLabRateLimiter(config)


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Mock, None, None]:
    """Mock asyncio.sleep to avoid actual delays in tests."""
    with patch("gitlab.clients.rate_limiter.limiter.asyncio.sleep") as m:
        yield m


class TestGitLabRateLimiter:
    @pytest.mark.asyncio
    async def test_context_manager_acquires_and_releases_semaphore(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test that context manager properly acquires and releases semaphore."""
        # Semaphore starts with max_concurrent permits
        assert rate_limiter._semaphore._value == 5

        async with rate_limiter:
            # One permit acquired
            assert rate_limiter._semaphore._value == 4

        # Permit released
        assert rate_limiter._semaphore._value == 5

    @pytest.mark.asyncio
    async def test_no_pause_when_rate_limit_info_is_none(
        self, rate_limiter: GitLabRateLimiter, mock_sleep: Mock
    ) -> None:
        """Test no pause occurs when rate limit info hasn't been set."""
        async with rate_limiter:
            pass

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pause_when_remaining_above_threshold(
        self, rate_limiter: GitLabRateLimiter, mock_sleep: Mock
    ) -> None:
        """Test no pause when remaining requests > max_concurrent."""
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000,
            remaining=100,  # Well above max_concurrent of 5
            reset_time=int(time.time()) + 60,
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_when_remaining_at_threshold(
        self, rate_limiter: GitLabRateLimiter, mock_sleep: Mock
    ) -> None:
        """Test pause occurs when remaining == max_concurrent."""
        reset_delay = 10
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000,
            remaining=5,  # Equal to max_concurrent
            reset_time=int(time.time()) + reset_delay,
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_called_once()
        actual_delay = mock_sleep.call_args[0][0]
        assert actual_delay >= reset_delay - 1  # Allow 1s timing skew

    @pytest.mark.asyncio
    async def test_pause_when_remaining_below_threshold(
        self, rate_limiter: GitLabRateLimiter, mock_sleep: Mock
    ) -> None:
        """Test pause occurs when remaining < max_concurrent."""
        reset_delay = 15
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000,
            remaining=2,  # Below max_concurrent of 5
            reset_time=int(time.time()) + reset_delay,
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_called_once()
        actual_delay = mock_sleep.call_args[0][0]
        assert actual_delay >= reset_delay - 1

    @pytest.mark.asyncio
    async def test_rate_limit_info_cleared_after_pause(
        self, rate_limiter: GitLabRateLimiter, mock_sleep: Mock
    ) -> None:
        """Test rate limit info is reset after waiting."""
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000,
            remaining=1,
            reset_time=int(time.time()) + 5,
        )

        async with rate_limiter:
            pass

        # After pause, rate_limit_info should be cleared
        assert rate_limiter.rate_limit_info is None

    @pytest.mark.asyncio
    async def test_no_pause_when_reset_time_in_past(
        self, rate_limiter: GitLabRateLimiter, mock_sleep: Mock
    ) -> None:
        """Test no pause when reset time has already passed."""
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000,
            remaining=0,
            reset_time=int(time.time()) - 60,  # In the past
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_not_called()


class TestGitLabRateLimiterIsRateLimitResponse:
    @pytest.fixture
    def rate_limiter(self) -> GitLabRateLimiter:
        """Create a rate limiter for response checking tests."""
        return GitLabRateLimiter(GitLabRateLimiterConfig(max_concurrent=10))

    def test_429_is_rate_limit(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test 429 response is detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 429
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is True

    def test_403_with_exhausted_headers_is_rate_limit(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test 403 with exhausted rate limit headers is detected."""
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {
            "ratelimit-remaining": "0",
            "ratelimit-reset": "1609459200",
        }

        assert rate_limiter.is_rate_limit_response(response) is True

    def test_403_without_exhausted_headers_is_not_rate_limit(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test 403 without rate limit headers is not detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is False

    def test_403_with_remaining_requests_is_not_rate_limit(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test 403 with remaining requests is not a rate limit error."""
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {
            "ratelimit-remaining": "50",
            "ratelimit-reset": "1609459200",
        }

        assert rate_limiter.is_rate_limit_response(response) is False

    def test_200_is_not_rate_limit(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test 200 response is not detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is False

    def test_500_is_not_rate_limit(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test 500 response is not detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 500
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is False


class TestGitLabRateLimiterUpdateRateLimits:
    @pytest.fixture
    def rate_limiter(self) -> GitLabRateLimiter:
        """Create a rate limiter for update tests."""
        return GitLabRateLimiter(GitLabRateLimiterConfig(max_concurrent=10))

    def test_update_with_valid_headers(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test updating rate limits from valid response headers."""
        headers = httpx.Headers(
            {
                "ratelimit-limit": "60",
                "ratelimit-remaining": "45",
                "ratelimit-reset": str(int(time.time()) + 60),
            }
        )

        result = rate_limiter.update_rate_limits(headers)

        assert result is not None
        assert result.limit == 60
        assert result.remaining == 45
        assert rate_limiter.rate_limit_info is result

    def test_update_with_missing_headers(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test updating with missing headers returns None."""
        headers = httpx.Headers({"other-header": "value"})

        result = rate_limiter.update_rate_limits(headers)

        assert result is None
        assert rate_limiter.rate_limit_info is None

    def test_update_with_partial_headers(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test updating with partial headers returns None."""
        headers = httpx.Headers(
            {
                "ratelimit-limit": "60",
                # Missing remaining and reset
            }
        )

        result = rate_limiter.update_rate_limits(headers)

        assert result is None

    def test_update_overwrites_previous_info(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test that new headers overwrite previous rate limit info."""
        # Set initial info
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=100,
            remaining=50,
            reset_time=int(time.time()) + 30,
        )

        # Update with new headers
        headers = httpx.Headers(
            {
                "ratelimit-limit": "60",
                "ratelimit-remaining": "10",
                "ratelimit-reset": str(int(time.time()) + 120),
            }
        )
        result = rate_limiter.update_rate_limits(headers)

        assert result is not None
        assert result.limit == 60
        assert result.remaining == 10


class TestGitLabRateLimiterConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_semaphore(
        self, config: GitLabRateLimiterConfig, mock_sleep: Mock
    ) -> None:
        """Test that concurrent requests are limited by semaphore."""
        rate_limiter = GitLabRateLimiter(config)

        concurrent = 0
        max_seen = 0

        async def request() -> None:
            nonlocal concurrent, max_seen
            async with rate_limiter:
                concurrent += 1
                max_seen = max(max_seen, concurrent)
                await asyncio.sleep(0.01)  # Simulate work
                concurrent -= 1

        # Run more tasks than max_concurrent
        tasks = [asyncio.create_task(request()) for _ in range(config.max_concurrent * 2)]
        await asyncio.gather(*tasks)

        assert max_seen <= config.max_concurrent

    @pytest.mark.asyncio
    async def test_pause_blocks_other_tasks(self, mock_sleep: Mock) -> None:
        """Test that pause under lock blocks other tasks."""
        config = GitLabRateLimiterConfig(max_concurrent=5)
        rate_limiter = GitLabRateLimiter(config)

        order: list[str] = []

        async def task_a() -> None:
            order.append("A-enter")
            # Seed limiter so that __aenter__ will sleep
            rate_limiter.rate_limit_info = RateLimitInfo(
                remaining=0,
                limit=1000,
                reset_time=int(time.time()) + 5,
            )
            async with rate_limiter:
                order.append("A-acquired")
                await asyncio.sleep(0.01)
            order.append("A-exit")

        async def task_b() -> None:
            # Slightly delayed start to ensure it queues behind A
            await asyncio.sleep(0.001)
            order.append("B-enter")
            async with rate_limiter:
                order.append("B-acquired")
                await asyncio.sleep(0.01)
            order.append("B-exit")

        t1 = asyncio.create_task(task_a())
        t2 = asyncio.create_task(task_b())
        await asyncio.gather(t1, t2)

        # A should acquire and exit before B acquires (blocked by lock-held sleep)
        assert order.index("A-acquired") < order.index("B-acquired")
        assert order.index("A-exit") < order.index("B-acquired")
