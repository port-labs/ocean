import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from jira.rate_limiter import JiraRateLimiter


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestJiraRateLimiter:
    """Test suite for the JiraRateLimiter."""

    def test_initialization_sets_default_values(self) -> None:
        """Tests that JiraRateLimiter initializes with correct default values."""
        rate_limiter = JiraRateLimiter()

        assert rate_limiter._semaphore._value == 5  # default max_concurrent
        assert (
            rate_limiter._minimum_limit_remaining == 1
        )  # default minimum_limit_remaining
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._near_limit is False
        assert rate_limiter._reset_time is None
        assert rate_limiter._retry_after is None

    def test_initialization_with_custom_values(self) -> None:
        """Tests that JiraRateLimiter initializes with custom values."""
        rate_limiter = JiraRateLimiter(max_concurrent=10, minimum_limit_remaining=5)

        assert rate_limiter._semaphore._value == 10
        assert rate_limiter._minimum_limit_remaining == 5

    def test_seconds_until_reset_with_no_reset_time(self) -> None:
        """Tests seconds_until_reset returns 0 when reset_time is None."""
        rate_limiter = JiraRateLimiter()

        assert rate_limiter.seconds_until_reset == 0.0

    def test_seconds_until_reset_with_future_reset_time(self) -> None:
        """Tests seconds_until_reset calculates correctly for future reset time."""
        rate_limiter = JiraRateLimiter()
        future_time = time.time() + 60
        rate_limiter._reset_time = future_time

        seconds_until_reset = rate_limiter.seconds_until_reset
        assert 59 <= seconds_until_reset <= 60  # Allow for small timing differences

    def test_seconds_until_reset_with_past_reset_time(self) -> None:
        """Tests seconds_until_reset returns 0 for past reset time."""
        rate_limiter = JiraRateLimiter()
        past_time = time.time() - 60
        rate_limiter._reset_time = past_time

        assert rate_limiter.seconds_until_reset == 0.0

    @pytest.mark.asyncio
    async def test_update_rate_limit_headers_standard_headers(self) -> None:
        """Tests update_rate_limit_headers with standard Jira headers."""
        rate_limiter = JiraRateLimiter()
        reset_time_iso = "2024-01-01T12:00:00Z"
        expected_timestamp = datetime.fromisoformat(
            reset_time_iso.replace("Z", "+00:00")
        ).timestamp()

        headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "50",
                "X-RateLimit-NearLimit": "false",
                "X-RateLimit-Reset": reset_time_iso,
                "Retry-After": "30",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers)

        assert rate_limiter._limit == 100
        assert rate_limiter._remaining == 50
        assert rate_limiter._near_limit is False
        assert (
            rate_limiter._reset_time
            and abs(rate_limiter._reset_time - expected_timestamp) < 0.01
        )
        assert rate_limiter._retry_after == 30.0

    @pytest.mark.asyncio
    async def test_update_rate_limit_headers_beta_headers(self) -> None:
        """Tests update_rate_limit_headers with beta-prefixed Jira headers."""
        rate_limiter = JiraRateLimiter()
        reset_time_iso = "2024-01-01T12:00:00Z"

        headers = httpx.Headers(
            {
                "X-Beta-RateLimit-Limit": "200",
                "X-Beta-RateLimit-Remaining": "25",
                "X-Beta-RateLimit-NearLimit": "true",
                "X-Beta-RateLimit-Reset": reset_time_iso,
                "Beta-Retry-After": "60",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers)

        assert rate_limiter._limit == 200
        assert rate_limiter._remaining == 25
        assert rate_limiter._near_limit is True
        assert rate_limiter._retry_after == 60.0

    @pytest.mark.asyncio
    async def test_update_rate_limit_headers_mixed_headers(self) -> None:
        """Tests update_rate_limit_headers prefers standard over beta headers."""
        rate_limiter = JiraRateLimiter()

        headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "100",
                "X-Beta-RateLimit-Limit": "200",
                "X-Beta-RateLimit-Remaining": "25",
                "X-RateLimit-NearLimit": "false",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers)

        assert rate_limiter._limit == 100
        assert rate_limiter._remaining == 25
        assert rate_limiter._near_limit is False

    @pytest.mark.asyncio
    @patch("jira.rate_limiter.logger")
    async def test_update_rate_limit_headers_with_reason(
        self, mock_logger: AsyncMock
    ) -> None:
        """Tests update_rate_limit_headers logs rate limit reason when present."""
        rate_limiter = JiraRateLimiter()

        headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-NearLimit": "true",
                "X-RateLimit-Reset": "2024-01-01T12:00:00Z",
                "RateLimit-Reason": "jira-quota-based",
                "Retry-After": "30",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers)

        # The rate limiter always calls warning if the reason_key exists (which it always does)
        mock_logger.warning.assert_called_once_with(
            "Rate limit breached for this reason: jira-quota-based"
        )

    @pytest.mark.asyncio
    @patch("jira.rate_limiter.logger")
    async def test_update_rate_limit_headers_handles_exceptions(
        self, mock_logger: AsyncMock
    ) -> None:
        """Tests update_rate_limit_headers handles parsing exceptions gracefully."""
        rate_limiter = JiraRateLimiter()

        # Headers with invalid values that will cause parsing errors
        headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "invalid_number",
                "X-RateLimit-Remaining": "also_invalid",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers)

        mock_logger.error.assert_called_once()
        assert "Failed to update rate limit headers:" in str(
            mock_logger.error.call_args
        )

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_near_limit_flag_set(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """Tests proactive sleep when near_limit flag is set."""
        reset_time = time.time() + 10.0
        rate_limiter = JiraRateLimiter()

        # Set near_limit flag and reset time
        rate_limiter._near_limit = True
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 10.0) < 0.01

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_remaining_below_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests proactive sleep when remaining requests are below threshold."""
        reset_time = time.time() + 5.0
        rate_limiter = JiraRateLimiter(minimum_limit_remaining=10)

        # Set remaining below threshold
        rate_limiter._limit = 100
        rate_limiter._remaining = 5  # Below threshold of 10
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 5.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 5.0) < 0.01

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_proactive_wait_when_above_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests no proactive sleep when remaining requests are above threshold."""
        rate_limiter = JiraRateLimiter(minimum_limit_remaining=5)

        # Set remaining above threshold
        rate_limiter._limit = 100
        rate_limiter._remaining = 10
        rate_limiter._near_limit = False

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_proactive_wait_when_reset_time_in_past(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests no proactive sleep when reset time is in the past."""
        rate_limiter = JiraRateLimiter(minimum_limit_remaining=5)

        # Set conditions that would normally trigger sleep, but with past reset time
        rate_limiter._limit = 100
        rate_limiter._remaining = 1
        rate_limiter._reset_time = time.time() - 60

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_concurrent_requests_are_limited_by_semaphore(self) -> None:
        """Tests that the semaphore correctly limits concurrent requests."""
        concurrent_limit = 3
        rate_limiter = JiraRateLimiter(max_concurrent=concurrent_limit)

        active_tasks = 0
        max_active_tasks = 0
        lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal active_tasks, max_active_tasks
            async with rate_limiter:
                async with lock:
                    active_tasks += 1
                    max_active_tasks = max(max_active_tasks, active_tasks)

                await asyncio.sleep(0.01)

                async with lock:
                    active_tasks -= 1

        # Create more tasks than the concurrent limit
        tasks = [worker() for _ in range(concurrent_limit + 2)]
        await asyncio.gather(*tasks)

        assert max_active_tasks == concurrent_limit

    @pytest.mark.asyncio
    async def test_context_manager_releases_semaphore_on_exception(self) -> None:
        """Tests that semaphore is released even when exception occurs."""
        rate_limiter = JiraRateLimiter(max_concurrent=1)

        # First, verify semaphore is available
        assert rate_limiter._semaphore._value == 1

        # Use context manager with exception
        with pytest.raises(ValueError):
            async with rate_limiter:
                raise ValueError("Test exception")

        # Verify semaphore was released
        assert rate_limiter._semaphore._value == 1

    @pytest.mark.asyncio
    async def test_multiple_sequential_context_entries(self) -> None:
        """Tests that multiple sequential uses of context manager work correctly."""
        rate_limiter = JiraRateLimiter(max_concurrent=1)

        # Use context manager multiple times sequentially
        for i in range(3):
            async with rate_limiter:
                assert rate_limiter._semaphore._value == 0
            assert rate_limiter._semaphore._value == 1

    @pytest.mark.asyncio
    async def test_reset_time_parsing_with_different_iso_formats(self) -> None:
        """Tests reset time parsing with different ISO 8601 formats."""
        rate_limiter = JiraRateLimiter()

        # Test with Z suffix
        headers_z = httpx.Headers(
            {
                "X-RateLimit-Reset": "2024-01-01T12:00:00Z",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "50",
                "X-RateLimit-NearLimit": "false",
                "Retry-After": "30",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers_z)
        expected_timestamp = datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc
        ).timestamp()
        assert (
            rate_limiter._reset_time
            and abs(rate_limiter._reset_time - expected_timestamp) < 0.01
        )

        # Test with +00:00 suffix
        headers_offset = httpx.Headers(
            {
                "X-RateLimit-Reset": "2024-01-01T12:00:00+00:00",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "50",
                "X-RateLimit-NearLimit": "false",
                "Retry-After": "30",
            }
        )

        await rate_limiter.update_rate_limit_headers(headers_offset)
        assert (
            rate_limiter._reset_time
            and abs(rate_limiter._reset_time - expected_timestamp) < 0.01
        )
