import asyncio
import time
from unittest.mock import AsyncMock, patch, create_autospec

import httpx
import pytest
from clients.rate_limiter import SentryRateLimiter


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestSentryRateLimiter:
    """Test suite for the SentryRateLimiter."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_threshold_reached(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the client proactively sleeps when the remaining requests
        are at or below the configured threshold upon entering the context manager.
        """

        reset_time = time.time() + 10.0
        rate_limiter = SentryRateLimiter(minimum_limit_remaining=5)

        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = reset_time

        response = create_autospec(httpx.Response, instance=True)
        response.status_code = 200
        mock_client.get.return_value = response

        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:

                await mock_client.get("https://test.com")

        mock_sleep.assert_awaited_once()

        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert (
            abs(calculated_sleep_duration - 10.0) < 0.01
        ), "Sleep duration is incorrect"

    async def test_update_rate_limits_parses_headers_correctly(self) -> None:
        """
        Tests that _update_rate_limits correctly parses headers and updates state.
        """
        reset_time_ms = (time.time() + 60) * 1000
        headers: httpx.Headers = httpx.Headers(
            {
                "X-Sentry-Rate-Limit-Limit": "100",
                "X-Sentry-Rate-Limit-Remaining": "10",
                "X-Sentry-Rate-Limit-Reset": str(reset_time_ms),
            }
        )
        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.headers = headers

        rate_limiter = SentryRateLimiter()
        await rate_limiter._update_rate_limits(mock_response.headers)

        assert rate_limiter._limit == 100
        assert rate_limiter._remaining == 10

        assert rate_limiter._reset_time is not None
        assert abs(rate_limiter._reset_time - reset_time_ms) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_is_skipped_if_reset_in_past(
        self,
        mock_sleep: AsyncMock,
    ) -> None:
        """
        Tests that the client does not sleep if the reset time is in the past,
        even if the remaining count is low.
        """
        rate_limiter = SentryRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = time.time() - 60

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_concurrent_requests_are_limited_by_semaphore(self) -> None:
        """
        Tests that the semaphore limits the number of concurrent requests.
        """
        concurrent_limit = 10
        rate_limiter = SentryRateLimiter(max_concurrent=concurrent_limit)

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

        tasks = [worker() for _ in range(concurrent_limit + 5)]
        await asyncio.gather(*tasks)

        assert max_active_tasks == concurrent_limit


@pytest.mark.parametrize(
    "retries, max_retries, should_retry, test_description",
    [
        (0, 3, True, "should retry on the first attempt"),
        (2, 3, True, "should retry when under max_retries"),
        (4, 3, False, "should not retry when at max_retries"),
    ],
)
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_handle_rate_limit_error_logic(
    mock_sleep: AsyncMock,
    retries: int,
    max_retries: int,
    should_retry: bool,
    test_description: str,
) -> None:
    """
    Tests the retry logic within _handle_rate_limit_error, checking both
    successful retries and failures when the max retry count is exceeded.
    """
    reset_time_in_header = time.time() + 10
    headers = {
        "X-Sentry-Rate-Limit-Remaining": "0",
        "X-Sentry-Rate-Limit-Reset": str(reset_time_in_header),
    }
    mock_response = create_autospec(httpx.Response, instance=True)
    mock_response.headers = headers
    mock_response.status_code = 429

    rate_limiter = SentryRateLimiter(max_retries=max_retries)
    rate_limiter._retries = retries

    with patch("time.time", return_value=reset_time_in_header - 10):
        result = await rate_limiter._handle_rate_limit_error(mock_response)
        assert result is should_retry, f"Failed scenario: {test_description}"
        assert rate_limiter._retries == retries + 1

    if should_retry:
        mock_sleep.assert_awaited_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert abs(sleep_duration - 10.5) == 10
    else:
        mock_sleep.assert_not_awaited()
