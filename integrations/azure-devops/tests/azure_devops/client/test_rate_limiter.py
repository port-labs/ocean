import asyncio
import time
from unittest.mock import AsyncMock, patch, create_autospec

import httpx
import pytest
from azure_devops.client.rate_limiter import AzureDevOpsRateLimiter


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestAzureDevOpsRateLimiter:
    """Test suite for the AzureDevOpsRateLimiter."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_threshold_reached(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the client proactively sleeps when the remaining requests
        are at or below the configured threshold upon entering the context manager.
        """
        reset_time = time.time() + 10.0
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)

        # Manually set the internal state to simulate low-remaining requests
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining
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

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_below_threshold(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the client proactively sleeps when the remaining requests
        are below the configured threshold.
        """
        reset_time = time.time() + 15.0
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)

        # Set remaining below threshold
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 15.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 15.0) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_wait_takes_precedence(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        Tests that retry-after wait takes precedence over proactive wait
        when both conditions are met.
        """
        reset_time = time.time() + 20.0
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)

        # Set both conditions: low remaining AND reset time (retry-after scenario)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 20.0):
            async with rate_limiter:
                pass

        # Should sleep for retry-after duration
        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 20.0) < 0.01

    async def test_update_from_headers_parses_headers_correctly(self) -> None:
        """
        Tests that update_from_headers correctly parses Azure DevOps headers
        and updates the limiter's state.
        """
        reset_time = time.time() + 60
        headers: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "200",
                "X-RateLimit-Remaining": "50",
                "X-RateLimit-Reset": str(reset_time),
            }
        )

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        assert rate_limiter._limit == 200
        assert rate_limiter._remaining == 50
        assert rate_limiter._reset_time is not None
        assert abs(rate_limiter._reset_time - reset_time) < 0.01

    async def test_update_from_headers_with_partial_headers(self) -> None:
        """
        Tests that update_from_headers handles partial headers correctly.
        """
        headers: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "200",
                # Missing X-RateLimit-Remaining
                "X-RateLimit-Reset": str(time.time() + 60),
            }
        )

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        # Should not update limit/remaining if both aren't present
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        # But should still update reset time
        assert rate_limiter._reset_time is not None

    async def test_update_from_headers_with_invalid_values(self) -> None:
        """
        Tests that update_from_headers handles invalid header values gracefully.
        """
        headers: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "invalid",
                "X-RateLimit-Remaining": "also_invalid",
                "X-RateLimit-Reset": "not_a_number",
            }
        )

        rate_limiter = AzureDevOpsRateLimiter()
        # Should not raise an exception
        await rate_limiter.update_from_headers(headers)

        # Values should remain None due to parsing errors
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    async def test_update_from_headers_with_empty_headers(self) -> None:
        """
        Tests that update_from_headers handles empty headers correctly.
        """
        headers: httpx.Headers = httpx.Headers({})

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        # Values should remain None
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_is_skipped_if_reset_in_past(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        Tests that the client does not sleep if the reset time is in the past,
        even if the remaining request count is low.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        # Set reset time to 60 seconds in the past
        rate_limiter._reset_time = time.time() - 60

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_wait_when_remaining_above_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        Tests that the client does not sleep when remaining requests
        are above the threshold.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining + 10
        rate_limiter._reset_time = time.time() + 60

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_wait_when_no_rate_limit_info(self, mock_sleep: AsyncMock) -> None:
        """
        Tests that the client does not sleep when no rate limit information
        has been received.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        # Don't set any rate limit state

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    async def test_concurrent_requests_are_limited_by_semaphore(self) -> None:
        """
        Tests that the semaphore correctly limits the number of concurrent requests.
        """
        concurrent_limit = 10
        rate_limiter = AzureDevOpsRateLimiter(max_concurrent=concurrent_limit)

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

    async def test_default_initialization_values(self) -> None:
        """
        Tests that the rate limiter initializes with correct default values.
        """
        rate_limiter = AzureDevOpsRateLimiter()

        assert rate_limiter._minimum_limit_remaining == 1
        assert rate_limiter._semaphore._value == 15  # Default max_concurrent
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    async def test_custom_initialization_values(self) -> None:
        """
        Tests that the rate limiter initializes with custom values correctly.
        """
        max_concurrent = 25
        minimum_limit_remaining = 10
        rate_limiter = AzureDevOpsRateLimiter(
            max_concurrent=max_concurrent,
            minimum_limit_remaining=minimum_limit_remaining,
        )

        assert rate_limiter._minimum_limit_remaining == minimum_limit_remaining
        assert rate_limiter._semaphore._value == max_concurrent

    async def test_seconds_until_reset_property(self) -> None:
        """
        Tests the seconds_until_reset property calculation.
        """
        rate_limiter = AzureDevOpsRateLimiter()

        # Test with no reset time
        assert rate_limiter.seconds_until_reset == 0.0

        # Test with future reset time
        future_time = time.time() + 30
        rate_limiter._reset_time = future_time
        assert abs(rate_limiter.seconds_until_reset - 30.0) < 1.0

        # Test with past reset time
        past_time = time.time() - 30
        rate_limiter._reset_time = past_time
        assert rate_limiter.seconds_until_reset == 0.0

    async def test_should_wait_for_retry_after_property(self) -> None:
        """
        Tests the should_wait_for_retry_after property calculation.
        """
        rate_limiter = AzureDevOpsRateLimiter()

        # Test with no reset time
        assert rate_limiter.should_wait_for_retry_after == 0.0

        # Test with future reset time
        future_time = time.time() + 45
        rate_limiter._reset_time = future_time
        assert abs(rate_limiter.should_wait_for_retry_after - 45.0) < 1.0

        # Test with past reset time
        past_time = time.time() - 45
        rate_limiter._reset_time = past_time
        assert rate_limiter.should_wait_for_retry_after == 0.0

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_state_reset_after_proactive_wait(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        Tests that rate limit state is reset after proactive waiting.
        """
        reset_time = time.time() + 10.0
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)

        # Set initial state
        rate_limiter._limit = 200
        rate_limiter._remaining = 1
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:
                pass

        # State should be reset after waiting
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_state_reset_after_retry_after_wait(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        Tests that reset time is cleared after retry-after waiting.
        """
        reset_time = time.time() + 5.0
        rate_limiter = AzureDevOpsRateLimiter()

        # Set reset time for retry-after scenario
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 5.0):
            async with rate_limiter:
                pass

        # Reset time should be cleared after waiting
        assert rate_limiter._reset_time is None

    async def test_context_manager_semaphore_release_on_exception(self) -> None:
        """
        Tests that the semaphore is properly released even when an exception occurs.
        """
        rate_limiter = AzureDevOpsRateLimiter(max_concurrent=5)
        initial_semaphore_value = rate_limiter._semaphore._value

        try:
            async with rate_limiter:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Semaphore should be released despite the exception
        assert rate_limiter._semaphore._value == initial_semaphore_value

    async def test_multiple_header_updates(self) -> None:
        """
        Tests that multiple header updates work correctly.
        """
        rate_limiter = AzureDevOpsRateLimiter()

        # First update
        headers1: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "200",
                "X-RateLimit-Remaining": "100",
            }
        )
        await rate_limiter.update_from_headers(headers1)
        assert rate_limiter._limit == 200
        assert rate_limiter._remaining == 100

        # Second update with different values
        headers2: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "200",
                "X-RateLimit-Remaining": "50",
                "X-RateLimit-Reset": str(time.time() + 30),
            }
        )
        await rate_limiter.update_from_headers(headers2)
        assert rate_limiter._limit == 200
        assert rate_limiter._remaining == 50
        assert rate_limiter._reset_time is not None
