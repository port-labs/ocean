import asyncio
import time
from unittest.mock import AsyncMock, patch, create_autospec

import httpx
import pytest
from clients.rate_limiter import SentryRateLimiter

# Mark all tests in this file as asyncio
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
        # 1. Setup: Define a reset time in the future.
        reset_time = time.time() + 10.0
        rate_limiter = SentryRateLimiter(minimum_limit_remaining=5)

        # Manually set the limiter's state to simulate it being near the rate limit.
        rate_limiter._rate_limit_remaining = (
            rate_limiter._minimum_limit_remaining - 1
        )  # e.g., 4
        rate_limiter._rate_limit_reset = reset_time

        # The response for the upcoming request should be successful (not 429).
        response = create_autospec(httpx.Response, instance=True)
        response.status_code = 200
        response.headers = {
            "X-Sentry-Rate-Limit-Remaining": "1",
            "X-Sentry-Rate-Limit-Reset": str(reset_time),
        }
        mock_client.get.return_value = response

        # 2. Execution: Patch time.time() to have a predictable sleep duration.
        # The proactive sleep should be triggered in __aenter__ before the request is made.
        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter as limiter:
                # The sleep happens on entry, before this line is executed.
                resp = await mock_client.get("https://test.com")
                # The limiter requires the response to be set for __aexit__ to process it.
                limiter._last_response = resp

        # 3. Assertion: Verify that sleep was called once with the correct duration.
        mock_sleep.assert_awaited_once()

        # Check that the sleep duration is correct (reset_time - current_time).
        # We expect abs(10.0 - calculated_sleep) to be very small.
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 10.0) < 0.01

    async def test_successful_request_updates_state(
        self, mock_client: AsyncMock
    ) -> None:
        """
        Tests that a successful request updates the internal rate limit state.
        """
        headers = {
            "X-Sentry-Rate-Limit-Remaining": "49",
            "X-Sentry-Rate-Limit-Reset": str(time.time() + 60),
        }
        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 200
        mock_response.headers = headers
        mock_client.get.return_value = mock_response

        rate_limiter = SentryRateLimiter()
        async with rate_limiter:
            mock_client.get.assert_awaited_once_with("https://test.com")
            assert (
                rate_limiter._last_response
                and rate_limiter._last_response.status_code == 200
            )
            assert rate_limiter._rate_limit_remaining == 49
            assert (
                rate_limiter._rate_limit_reset
                and abs(
                    rate_limiter._rate_limit_reset
                    - float(headers["X-Sentry-Rate-Limit-Reset"])
                )
                < 0.01
            )

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
        rate_limiter._rate_limit_remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._rate_limit_reset = time.time() - 60

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reactive_retry_on_429_with_retry_after_header(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the client retries after a 429 response, respecting
        the 'Retry-After' header, by returning True from __aexit__.
        """
        retry_after_seconds = 10.0
        mock_429_response = create_autospec(httpx.Response, instance=True)
        mock_429_response.status_code = 429
        mock_429_response.headers = {"Retry-After": str(retry_after_seconds)}
        mock_client.get.return_value = mock_429_response

        http_error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=create_autospec(httpx.Request, instance=True),
            response=mock_429_response,
        )
        mock_429_response.raise_for_status.side_effect = http_error

        rate_limiter = SentryRateLimiter()
        await rate_limiter.__aenter__()

        # 3. Call __aexit__ directly with the simulated exception info
        async with rate_limiter:
            await mock_client.get("https://test.com")
        should_retry = await rate_limiter.__aexit__(
            exc_type=httpx.HTTPStatusError, exc_val=http_error, exc_tb=None
        )
        # 4. Assert the outcome
        # The method should return True to signal that the operation should be retried.
        assert should_retry is True

        # It should have slept for the duration specified in the header.
        mock_sleep.assert_awaited_once()
        assert abs(mock_sleep.call_args.args[0] - retry_after_seconds) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reactive_retry_on_429_with_exponential_backoff(
        self,
        mock_sleep: AsyncMock,
    ) -> None:
        """
        Tests that the client falls back to exponential backoff if a 429
        response is missing the 'Retry-After' header.
        """
        mock_429_response = create_autospec(httpx.Response, instance=True)
        mock_429_response.status_code = 429
        mock_429_response.headers = {}

        rate_limiter = SentryRateLimiter()
        rate_limiter._last_response = mock_429_response

        # Call __aexit__ directly for the first retry attempt
        should_retry_1 = await rate_limiter.__aexit__(
            exc_type=None, exc_val=None, exc_tb=None
        )

        assert should_retry_1 is True
        mock_sleep.assert_awaited_once_with(2**1)

        mock_sleep.reset_mock()
        rate_limiter._last_response = mock_429_response

        # Call __aexit__ for the second retry attempt
        should_retry_2 = await rate_limiter.__aexit__(
            exc_type=None, exc_val=None, exc_tb=None
        )

        assert should_retry_2 is True
        mock_sleep.assert_awaited_once_with(2**2)

    async def test_non_429_http_error_does_not_retry(self) -> None:
        """
        Tests that a non-429 HTTP error is not handled by __aexit__
        and therefore does not trigger a retry.
        """
        mock_500_response = create_autospec(httpx.Response, instance=True)
        mock_500_response.status_code = 500
        mock_500_response.headers = {}
        mock_500_response.text = "Internal Server Error"

        rate_limiter = SentryRateLimiter()
        rate_limiter._last_response = mock_500_response

        should_retry = await rate_limiter.__aexit__(
            exc_type=None, exc_val=None, exc_tb=None
        )

        assert should_retry is False

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_concurrent_requests_with_semaphore(
        self, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the semaphore limits the number of concurrent requests.
        """
        concurrent_limit = 2
        rate_limiter = SentryRateLimiter(concurrent_requests=concurrent_limit)

        async def worker() -> None:
            async with rate_limiter:
                await mock_client.get("https://test.com")

        # Use a list of futures to simulate multiple requests
        tasks = [worker() for _ in range(concurrent_limit + 1)]

        # Use a mock for the semaphore to check if it's being acquired
        with patch.object(
            rate_limiter._semaphore, "acquire", new_callable=AsyncMock
        ) as mock_acquire:
            await asyncio.gather(*tasks)
            # The `acquire` should be called for each task
            assert mock_acquire.call_count == concurrent_limit + 1

    async def test_lock_is_used_for_state_updates(self) -> None:
        """
        Verifies that the asyncio.Lock is acquired during state updates
        to ensure thread-safety in concurrent environments.
        """
        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 200
        mock_response.headers = {"X-Sentry-Rate-Limit-Remaining": "10"}

        rate_limiter = SentryRateLimiter()

        with (
            patch.object(
                rate_limiter._lock, "acquire", new_callable=AsyncMock
            ) as mock_acquire,
            patch.object(rate_limiter._lock, "release") as mock_release,
        ):
            async with rate_limiter:
                rate_limiter._last_response = mock_response

            # The lock is acquired in __aenter__ and released in __aexit__
            assert mock_acquire.call_count == 1
            assert mock_release.call_count == 1
