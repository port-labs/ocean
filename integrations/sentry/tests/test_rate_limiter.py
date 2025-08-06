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
            async with rate_limiter:
                # The sleep happens on entry, before this line is executed.
                await mock_client.get("https://test.com")

        # 3. Assertion: Verify that sleep was called once with the correct duration.
        mock_sleep.assert_awaited_once()

        # Check that the sleep duration is correct (reset_time - current_time).
        # We expect abs(10.0 - calculated_sleep) to be very small.
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 10.0) < 0.01

    async def test_unsuccessful_request_updates_state(
        self, mock_client: AsyncMock
    ) -> None:
        """
        Tests that an unsuccessful request (429) updates the internal rate limit state.
        """
        headers = {
            "X-Sentry-Rate-Limit-Remaining": "1",
            "X-Sentry-Rate-Limit-Reset": str(time.time() + 60),
            "Retry-After": "30",
        }
        mock_response = create_autospec(httpx.Response, instance=True)
        mock_response.status_code = 429
        mock_response.headers = headers
        mock_client.get.return_value = mock_response

        rate_limiter = SentryRateLimiter()
        await rate_limiter._update_rate_limit_state(mock_response)
        assert rate_limiter._rate_limit_remaining == 1
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


@pytest.mark.parametrize(
    "headers, retries, max_duration, expected_duration, test_description",
    [
        (
            {"Retry-After": "30"},
            1,
            60,
            30.0,
            "uses Retry-After header when present",
        ),
        (
            {"Retry-After": "invalid"},
            2,
            60,
            4.0,  # 2^2 = 4
            "falls back to exponential backoff when Retry-After is invalid",
        ),
        (
            {},
            3,
            60,
            8.0,  # 2^3 = 8
            "uses exponential backoff when Retry-After is missing",
        ),
        (
            {"Retry-After": "100"},
            1,
            5,
            5.0,  # capped by maximum_sleep_duration
            "respects maximum sleep duration cap",
        ),
        (
            {"Retry-After": "0"},
            1,
            60,
            0.0,
            "handles zero Retry-After value",
        ),
    ],
)
async def test_get_sleep_retry_duration(
    headers: dict[str, str],
    retries: int,
    max_duration: int,
    expected_duration: float,
    test_description: str,
) -> None:
    """Test different scenarios for sleep duration calculation."""
    mock_response = create_autospec(httpx.Response, instance=True)
    mock_response.headers = headers

    rate_limiter = SentryRateLimiter(maximum_sleep_duration=max_duration)
    rate_limiter._retries = retries

    duration = rate_limiter._get_sleep_retry_duration(mock_response)

    assert duration == expected_duration, f"Failed scenario: {test_description}"


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_concurrent_requests_with_semaphore(mock_client: AsyncMock) -> None:
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


@pytest.mark.parametrize(
    "retries, max_retries, retry_after, expected_result, test_description",
    [
        (
            0,
            3,
            "30",
            True,
            "should retry on first attempt",
        ),
        (
            2,
            3,
            "30",
            True,
            "should retry when under max_retries",
        ),
        (
            3,
            3,
            "30",
            False,
            "should not retry when max_retries reached",
        ),
    ],
)
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_handle_rate_limit(
    mock_sleep: AsyncMock,
    retries: int,
    max_retries: int,
    retry_after: str,
    expected_result: bool,
    test_description: str,
) -> None:
    """Test rate limit handling with different retry scenarios."""
    # Setup
    headers = {
        "Retry-After": retry_after,
        "X-Sentry-Rate-Limit-Remaining": "0",
        "X-Sentry-Rate-Limit-Reset": str(time.time() + 60),
    }
    mock_response = create_autospec(httpx.Response, instance=True)
    mock_response.headers = headers
    mock_response.status_code = 429

    rate_limiter = SentryRateLimiter(maximum_retries=max_retries)
    rate_limiter._retries = retries

    # Execute
    result = await rate_limiter._handle_rate_limit(mock_response)

    # Verify
    assert result == expected_result, f"Failed scenario: {test_description}"

    if expected_result:
        # Should sleep when retrying
        mock_sleep.assert_awaited_once()
        # Verify retry counter was incremented
        assert rate_limiter._retries == retries + 1
    else:
        # Should update rate limit state but not sleep when max retries exceeded
        assert rate_limiter._rate_limit_remaining == 0
        mock_sleep.assert_not_awaited()


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_handle_rate_limit_updates_state_when_max_retries_exceeded(
    mock_sleep: AsyncMock,
) -> None:
    """Test that rate limit state is updated when max retries are exceeded."""
    # Setup
    reset_time = time.time() + 60
    headers = {
        "Retry-After": "30",
        "X-Sentry-Rate-Limit-Remaining": "0",
        "X-Sentry-Rate-Limit-Reset": str(reset_time),
    }
    mock_response = create_autospec(httpx.Response, instance=True)
    mock_response.headers = headers
    mock_response.status_code = 429

    rate_limiter = SentryRateLimiter(maximum_retries=3)
    rate_limiter._retries = 3  # Already at max retries

    # Execute
    result = await rate_limiter._handle_rate_limit(mock_response)

    # Verify
    assert result is False
    assert rate_limiter._rate_limit_remaining == 0
    assert (
        rate_limiter._rate_limit_reset
        and abs(rate_limiter._rate_limit_reset - reset_time) < 0.01
    )
    mock_sleep.assert_not_awaited()
