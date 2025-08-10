import asyncio
import time
from unittest.mock import AsyncMock, patch, create_autospec

import httpx
import pytest
from rate_limiter import LaunchDarklyRateLimiter

# All tests in this file are for asynchronous code
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestLaunchDarklyRateLimiter:
    """Test suite for the LaunchDarklyRateLimiter."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_threshold_reached(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the client proactively sleeps when the remaining requests
        are at or below the configured threshold upon entering the context manager.
        """
        reset_time = time.time() + 10.0
        rate_limiter = LaunchDarklyRateLimiter(minimum_limit_remaining=5)

        # Manually set the internal state to simulate low-remaining requests
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = reset_time

        response = create_autospec(httpx.Response, instance=True)
        response.status_code = 200
        mock_client.get.return_value = response

        # Mock time to control the sleep duration calculation
        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:
                await mock_client.get("https://test.com")

        mock_sleep.assert_awaited_once()

        # Check that the sleep duration is correct
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert (
            abs(calculated_sleep_duration - 10.0) < 0.01
        ), "Sleep duration is incorrect"

    async def test_update_from_headers_parses_headers_correctly(self) -> None:
        """
        Tests that update_from_headers correctly parses headers and updates the limiter's state.
        """
        reset_time_ms = (time.time() + 60) * 1000
        headers: httpx.Headers = httpx.Headers(
            {
                "X-Ratelimit-Route-Limit": "100",
                "X-Ratelimit-Route-Remaining": "10",
                "X-Ratelimit-Reset": str(reset_time_ms),
            }
        )

        rate_limiter = LaunchDarklyRateLimiter()
        # Call the public method to update the state from headers
        await rate_limiter.update_from_headers(headers)

        assert rate_limiter._limit == 100
        assert rate_limiter._remaining == 10
        assert rate_limiter._reset_time is not None
        assert abs(rate_limiter._reset_time - (reset_time_ms / 1000)) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_is_skipped_if_reset_in_past(
        self,
        mock_sleep: AsyncMock,
    ) -> None:
        """
        Tests that the client does not sleep if the reset time is in the past,
        even if the remaining request count is low.
        """
        rate_limiter = LaunchDarklyRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        # Set reset time to 60 seconds in the past
        rate_limiter._reset_time = time.time() - 60

        async with rate_limiter:
            pass  # Enter and exit the context manager

        mock_sleep.assert_not_awaited()

    async def test_concurrent_requests_are_limited_by_semaphore(self) -> None:
        """
        Tests that the semaphore correctly limits the number of concurrent requests.
        """
        concurrent_limit = 10
        rate_limiter = LaunchDarklyRateLimiter(max_concurrent=concurrent_limit)

        active_tasks = 0
        max_active_tasks = 0
        lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal active_tasks, max_active_tasks
            async with rate_limiter:
                # Track the number of concurrently active tasks inside the context manager
                async with lock:
                    active_tasks += 1
                    max_active_tasks = max(max_active_tasks, active_tasks)

                await asyncio.sleep(0.01)

                async with lock:
                    active_tasks -= 1

        # Create more tasks than the concurrent limit to test the semaphore
        tasks = [worker() for _ in range(concurrent_limit + 5)]
        await asyncio.gather(*tasks)

        assert max_active_tasks == concurrent_limit
