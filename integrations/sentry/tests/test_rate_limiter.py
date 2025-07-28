import time
from unittest.mock import AsyncMock, patch, create_autospec

import httpx
import pytest
from clients.rate_limiter import (
    MAXIMUM_LIMIT_ON_RETRIES,
    MINIMUM_LIMIT_REMAINING,
    SentryRateLimiter,
)

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def rate_limiter(mock_client: AsyncMock) -> SentryRateLimiter:
    """Provides an instance of SentryRateLimiter with a mock client."""
    return SentryRateLimiter(client=mock_client)


class TestSentryRateLimiter:
    """Test suite for the SentryRateLimiter."""

    async def test_successful_request_updates_state(
        self, rate_limiter: SentryRateLimiter, mock_client: AsyncMock
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
        mock_response.json = AsyncMock(return_value={"data": "success"})
        mock_client.request.return_value = mock_response

        response = await rate_limiter.request("https://test.com")

        mock_client.request.assert_awaited_once_with(
            "GET", "https://test.com", params=None
        )
        assert response.status_code == 200
        assert await response.json() == {"data": "success"}
        assert rate_limiter._rate_limit_remaining == 49
        assert rate_limiter._rate_limit_reset == float(
            headers["X-Sentry-Rate-Limit-Reset"]
        )

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_threshold_reached(
        self,
        mock_sleep: AsyncMock,
        rate_limiter: SentryRateLimiter,
        mock_client: AsyncMock,
    ) -> None:
        """
        Tests that the client proactively sleeps when the remaining requests
        are below the configured threshold.
        """
        reset_time = time.time() + 10
        # Set the initial state to be below the threshold
        rate_limiter._rate_limit_remaining = MINIMUM_LIMIT_REMAINING - 1
        rate_limiter._rate_limit_reset = reset_time

        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json = AsyncMock(return_value={"data": "success"})
        mock_client.request.return_value = mock_response

        with patch("time.time", return_value=reset_time - 10):
            await rate_limiter.request("https://test.com")

        # Should sleep for the remaining time in the window
        mock_sleep.assert_awaited_once()
        # The sleep duration should be close to 10 seconds
        assert abs(mock_sleep.call_args[0][0] - 10) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_is_skipped_if_reset_in_past(
        self,
        mock_sleep: AsyncMock,
        rate_limiter: SentryRateLimiter,
        mock_client: AsyncMock,
    ) -> None:
        """
        Tests that the client does not sleep if the reset time is in the past,
        even if the remaining count is low.
        """
        # Set the initial state with a reset time that has already passed
        rate_limiter._rate_limit_remaining = MINIMUM_LIMIT_REMAINING - 1
        rate_limiter._rate_limit_reset = time.time() - 60

        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json = AsyncMock(return_value={"data": "success"})
        mock_client.request.return_value = mock_response

        await rate_limiter.request("https://test.com")

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reactive_retry_on_429_with_retry_after_header(
        self,
        mock_sleep: AsyncMock,
        rate_limiter: SentryRateLimiter,
        mock_client: AsyncMock,
    ) -> None:
        """
        Tests that the client retries after a 429 response, respecting
        the 'Retry-After' header.
        """
        retry_after_seconds = 0.1
        mock_429_response = create_autospec(httpx.Response, instance=True)
        mock_429_response.status_code = 429
        mock_429_response.headers = {"Retry-After": str(retry_after_seconds)}
        mock_429_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", response=mock_429_response, request=AsyncMock()
        )

        mock_200_response = create_autospec(httpx.Response, instance=True)
        mock_200_response.status_code = 200
        mock_200_response.headers = {}
        mock_200_response.json = AsyncMock(return_value={"data": "success"})
        mock_client.request.side_effect = [mock_429_response, mock_200_response]

        response = await rate_limiter.request("https://test.com")

        assert mock_client.request.call_count == 2
        mock_sleep.assert_awaited_once_with(retry_after_seconds)
        assert response.status_code == 200
        assert await response.json() == {"data": "success"}

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reactive_retry_on_429_with_exponential_backoff(
        self,
        mock_sleep: AsyncMock,
        rate_limiter: SentryRateLimiter,
        mock_client: AsyncMock,
    ) -> None:
        """
        Tests that the client falls back to exponential backoff if a 429
        response is missing the 'Retry-After' header.
        """
        mock_429_response = create_autospec(httpx.Response, instance=True)
        mock_429_response.status_code = 429
        mock_429_response.headers = {}
        mock_429_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", response=mock_429_response, request=AsyncMock()
        )

        mock_200_response = create_autospec(httpx.Response, instance=True)
        mock_200_response.status_code = 200
        mock_200_response.headers = {}
        mock_200_response.json = AsyncMock(return_value={"data": "success"})
        mock_client.request.side_effect = [mock_429_response, mock_200_response]

        await rate_limiter.request("https://test.com")

        assert mock_client.request.call_count == 2
        # Fallback sleep should be 2**1 for the first retry
        expected_sleep = 2**1
        mock_sleep.assert_awaited_once_with(expected_sleep)

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_max_retries_exceeded_raises_error(
        self,
        mock_sleep: AsyncMock,
        rate_limiter: SentryRateLimiter,
        mock_client: AsyncMock,
    ) -> None:
        """
        Tests that an HTTPStatusError is raised after exceeding the
        maximum number of retries for a 429 response.
        """
        # The client will always return 429
        mock_429_response = create_autospec(httpx.Response, instance=True)
        mock_429_response.status_code = 429
        mock_429_response.headers = {}

        mock_429_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", response=mock_429_response, request=AsyncMock()
        )

        mock_client.request.return_value = mock_429_response

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await rate_limiter.request("https://test.com")

        # The final error should be the 429
        assert exc_info.value.response.status_code == 429

        # Total calls = 1 initial + MAXIMUM_LIMIT_ON_RETRIES
        assert mock_client.request.call_count == MAXIMUM_LIMIT_ON_RETRIES + 1
        assert mock_sleep.call_count == MAXIMUM_LIMIT_ON_RETRIES

        mock_429_response.raise_for_status.assert_called_once()

        # Check exponential backoff sleep times
        sleep_calls = mock_sleep.await_args_list
        assert sleep_calls[0][0][0] == 2**1  # 1st retry
        assert sleep_calls[1][0][0] == 2**2  # 2nd retry
        assert sleep_calls[2][0][0] == 2**3  # 3rd retry

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_non_429_http_error_raises_immediately(
        self,
        mock_sleep: AsyncMock,
        rate_limiter: SentryRateLimiter,
        mock_client: AsyncMock,
    ) -> None:
        """
        Tests that a non-429 HTTP error is raised immediately without retries.
        """
        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.text = "Internal Server Error"

        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", response=mock_response, request=AsyncMock()
        )

        mock_client.request.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await rate_limiter.request("https://test.com")

        assert exc_info.value.response.status_code == 500
        mock_client.request.assert_awaited_once()
        mock_sleep.assert_not_awaited()
        mock_response.raise_for_status.assert_called_once()

    async def test_request_passes_method_and_params(
        self, rate_limiter: SentryRateLimiter, mock_client: AsyncMock
    ) -> None:
        """
        Tests that the `request` method correctly passes the HTTP method
        and query parameters to the underlying client.
        """
        mock_request = create_autospec(httpx.Response, instance=True)
        mock_request.status_code = 200
        mock_request.headers = {}
        mock_request.json = {"data": "success"}
        mock_client.request.return_value = mock_request

        url = "https://test.com/api"
        params = {"project": "test-project", "id": 123}

        await rate_limiter.request(url, method="POST", params=params)

        mock_client.request.assert_awaited_once_with("POST", url, params=params)

    async def test_lock_is_used_for_state_updates(
        self, rate_limiter: SentryRateLimiter, mock_client: AsyncMock
    ) -> None:
        """
        Verifies that the asyncio.Lock is acquired during state updates
        to ensure thread-safety in concurrent environments.
        """
        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 200
        mock_response.headers = {"X-Sentry-Rate-Limit-Remaining": "10"}
        mock_response.json = {"data": "success"}
        mock_client.request.return_value = mock_response

        # Patch the lock to spy on its calls
        with (
            patch.object(
                rate_limiter._lock, "acquire", new_callable=AsyncMock
            ) as mock_acquire,
            patch.object(rate_limiter._lock, "release") as mock_release,
        ):
            await rate_limiter.request("https://test.com")

            # _wait_if_needed and _update_rate_limit_state both acquire the lock
            assert mock_acquire.call_count == 2
            assert mock_release.call_count == 2
