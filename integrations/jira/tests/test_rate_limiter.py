import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from jira.rate_limiter import (
    JiraRateLimiter,
    JiraRateLimitInfo,
    is_rate_limit_response,
    MAX_CONCURRENT_REQUESTS,
    MINIMUM_LIMIT_REMAINING,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestJiraRateLimitInfo:
    """Tests for the JiraRateLimitInfo dataclass."""

    def test_seconds_until_reset_future(self) -> None:
        info = JiraRateLimitInfo(limit=100, remaining=50, reset_time=time.time() + 60)
        assert 59 <= info.seconds_until_reset <= 60

    def test_seconds_until_reset_past(self) -> None:
        info = JiraRateLimitInfo(limit=100, remaining=50, reset_time=time.time() - 60)
        assert info.seconds_until_reset == 0.0

    def test_is_expired_true(self) -> None:
        info = JiraRateLimitInfo(limit=100, remaining=50, reset_time=time.time() - 1)
        assert info.is_expired is True

    def test_is_expired_false(self) -> None:
        info = JiraRateLimitInfo(limit=100, remaining=50, reset_time=time.time() + 60)
        assert info.is_expired is False


class TestIsRateLimitResponse:
    """Tests for the is_rate_limit_response helper."""

    def test_429_is_rate_limited(self) -> None:
        response = httpx.Response(429)
        assert is_rate_limit_response(response) is True

    def test_200_is_not_rate_limited(self) -> None:
        response = httpx.Response(200)
        assert is_rate_limit_response(response) is False

    def test_403_is_not_rate_limited(self) -> None:
        response = httpx.Response(403)
        assert is_rate_limit_response(response) is False

    def test_500_is_not_rate_limited(self) -> None:
        response = httpx.Response(500)
        assert is_rate_limit_response(response) is False


class TestJiraRateLimiter:
    """Test suite for the JiraRateLimiter."""

    def test_initialization_sets_default_values(self) -> None:
        """Tests that JiraRateLimiter initializes with correct default values."""
        rate_limiter = JiraRateLimiter()

        assert rate_limiter._semaphore._value == MAX_CONCURRENT_REQUESTS
        assert rate_limiter._minimum_limit_remaining == MINIMUM_LIMIT_REMAINING
        assert rate_limiter._rate_limit_info is None
        assert rate_limiter._near_limit is False
        assert rate_limiter._retry_after is None
        assert rate_limiter._initialized is False

    def test_initialization_with_custom_values(self) -> None:
        """Tests that JiraRateLimiter initializes with custom values."""
        rate_limiter = JiraRateLimiter(max_concurrent=10, minimum_limit_remaining=5)

        assert rate_limiter._semaphore._value == 10
        assert rate_limiter._minimum_limit_remaining == 5

    def test_seconds_until_reset_with_no_info(self) -> None:
        """Tests seconds_until_reset returns 0 when no rate limit info exists."""
        rate_limiter = JiraRateLimiter()
        assert rate_limiter.seconds_until_reset == 0.0

    def test_seconds_until_reset_with_future_reset_time(self) -> None:
        """Tests seconds_until_reset calculates correctly for future reset time."""
        rate_limiter = JiraRateLimiter()
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=50, reset_time=time.time() + 60
        )
        seconds = rate_limiter.seconds_until_reset
        assert 59 <= seconds <= 60

    def test_seconds_until_reset_with_past_reset_time(self) -> None:
        """Tests seconds_until_reset returns 0 for past reset time."""
        rate_limiter = JiraRateLimiter()
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=50, reset_time=time.time() - 60
        )
        assert rate_limiter.seconds_until_reset == 0.0

    # --- on_response tests (replaces update_rate_limit_headers tests) ---

    @pytest.mark.asyncio
    async def test_on_response_initializes_from_normal_response(self) -> None:
        """Tests on_response initializes rate limit state from a normal response."""
        rate_limiter = JiraRateLimiter()
        reset_time_iso = "2099-01-01T12:00:00Z"
        expected_timestamp = datetime.fromisoformat(
            reset_time_iso.replace("Z", "+00:00")
        ).timestamp()

        response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "50",
                "x-ratelimit-nearlimit": "false",
                "x-ratelimit-reset": reset_time_iso,
            },
        )

        await rate_limiter.on_response(response)

        assert rate_limiter._rate_limit_info is not None
        assert rate_limiter._rate_limit_info.limit == 100
        assert rate_limiter._rate_limit_info.remaining == 50
        assert abs(rate_limiter._rate_limit_info.reset_time - expected_timestamp) < 0.01
        assert rate_limiter._near_limit is False
        assert rate_limiter._initialized is True

    @pytest.mark.asyncio
    async def test_on_response_no_headers_is_noop(self) -> None:
        """Tests on_response is a no-op when no rate limit headers are present."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            200,
            headers={
                "content-type": "application/json",
            },
        )

        await rate_limiter.on_response(response)

        assert rate_limiter._rate_limit_info is None
        assert rate_limiter._initialized is False

    @pytest.mark.asyncio
    async def test_on_response_handles_429_rate_limit(self) -> None:
        """Tests on_response correctly handles a 429 rate-limited response."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            429,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "2099-01-01T12:00:00Z",
                "retry-after": "30",
            },
        )

        await rate_limiter.on_response(response)

        assert rate_limiter._rate_limit_info is not None
        assert rate_limiter._rate_limit_info.remaining == 0
        assert rate_limiter._retry_after == 30.0
        assert rate_limiter._initialized is True

    @pytest.mark.asyncio
    async def test_on_response_429_with_only_retry_after(self) -> None:
        """Tests 429 response with only retry-after header (no rate limit headers)."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            429,
            headers={
                "retry-after": "60",
            },
        )

        await rate_limiter.on_response(response)

        assert rate_limiter._rate_limit_info is not None
        assert rate_limiter._rate_limit_info.remaining == 0
        assert rate_limiter._retry_after == 60.0
        # reset_time should be ~60s from now
        assert rate_limiter._rate_limit_info.seconds_until_reset > 55

    @pytest.mark.asyncio
    @patch("jira.rate_limiter.logger")
    async def test_on_response_429_logs_with_reason(
        self, mock_logger: AsyncMock
    ) -> None:
        """Tests that 429 response logs the rate limit reason."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            429,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "2099-01-01T12:00:00Z",
                "retry-after": "30",
                "ratelimit-reason": "jira-quota-based",
            },
        )

        await rate_limiter.on_response(response)

        # The bound logger's warning should have been called with the reason
        mock_logger.bind.return_value.warning.assert_called_once()
        call_args = str(mock_logger.bind.return_value.warning.call_args)
        assert "jira-quota-based" in call_args

    @pytest.mark.asyncio
    async def test_on_response_does_not_regress_reset_time(self) -> None:
        """Tests that a 429 with an older reset time does not overwrite a newer one."""
        rate_limiter = JiraRateLimiter()

        # First, set a future reset time
        future_reset = time.time() + 120
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=0, reset_time=future_reset
        )
        rate_limiter._initialized = True

        # Now send a 429 with an older reset time
        response = httpx.Response(
            429,
            headers={
                "retry-after": "5",
            },
        )

        await rate_limiter.on_response(response)

        # The reset time should NOT have regressed
        assert rate_limiter._rate_limit_info.reset_time == future_reset

    # --- __aenter__ / enforce_rate_limit tests ---

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_near_limit_flag_set(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests proactive sleep when near_limit flag is set."""
        reset_time = time.time() + 10.0
        rate_limiter = JiraRateLimiter()

        rate_limiter._near_limit = True
        rate_limiter._initialized = True
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=50, reset_time=reset_time
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 10.0) < 1.0

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_when_remaining_below_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests proactive sleep when remaining requests are below threshold."""
        reset_time = time.time() + 5.0
        rate_limiter = JiraRateLimiter(minimum_limit_remaining=10)

        rate_limiter._initialized = True
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=5, reset_time=reset_time
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 5.0) < 1.0

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_proactive_wait_when_above_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests no proactive sleep when remaining requests are above threshold."""
        rate_limiter = JiraRateLimiter(minimum_limit_remaining=5)

        rate_limiter._initialized = True
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=10, reset_time=time.time() + 60
        )
        rate_limiter._near_limit = False

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_proactive_wait_when_not_initialized(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests no proactive sleep when rate limiter has not been initialized."""
        rate_limiter = JiraRateLimiter()

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_stale_state_reset_when_epoch_passes(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests that stale state is cleared when the rate limit window expires."""
        rate_limiter = JiraRateLimiter()

        # Set state as if we were rate limited, but the window has expired
        rate_limiter._initialized = True
        rate_limiter._near_limit = True
        rate_limiter._retry_after = 30.0
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=0, reset_time=time.time() - 10
        )

        async with rate_limiter:
            pass

        # Transient flags should be reset, but initialized and limit stay
        mock_sleep.assert_not_awaited()
        assert rate_limiter._initialized is True
        assert rate_limiter._near_limit is False
        assert rate_limiter._retry_after is None
        assert rate_limiter._rate_limit_info.remaining == 100  # restored to limit

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_triggers_sleep(self, mock_sleep: AsyncMock) -> None:
        """Tests that a non-zero retry_after causes a sleep."""
        rate_limiter = JiraRateLimiter()

        rate_limiter._initialized = True
        rate_limiter._retry_after = 15.0
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=0, reset_time=time.time() + 30
        )

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once_with(15.0)
        # After sleeping, retry_after should be cleared but state preserved
        assert rate_limiter._retry_after is None
        assert rate_limiter._initialized is True

    @pytest.mark.asyncio
    async def test_remaining_decremented_locally(self) -> None:
        """Tests that remaining is decremented after __aenter__."""
        rate_limiter = JiraRateLimiter()

        rate_limiter._initialized = True
        rate_limiter._rate_limit_info = JiraRateLimitInfo(
            limit=100, remaining=50, reset_time=time.time() + 60
        )

        async with rate_limiter:
            pass

        # remaining should have been decremented by 1
        assert rate_limiter._rate_limit_info.remaining == 49

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

        tasks = [worker() for _ in range(concurrent_limit + 2)]
        await asyncio.gather(*tasks)

        assert max_active_tasks == concurrent_limit

    @pytest.mark.asyncio
    async def test_context_manager_releases_semaphore_on_exception(self) -> None:
        """Tests that semaphore is released even when exception occurs."""
        rate_limiter = JiraRateLimiter(max_concurrent=1)

        assert rate_limiter._semaphore._value == 1

        with pytest.raises(ValueError):
            async with rate_limiter:
                raise ValueError("Test exception")

        assert rate_limiter._semaphore._value == 1

    @pytest.mark.asyncio
    async def test_multiple_sequential_context_entries(self) -> None:
        """Tests that multiple sequential uses of context manager work correctly."""
        rate_limiter = JiraRateLimiter(max_concurrent=1)

        for i in range(3):
            async with rate_limiter:
                assert rate_limiter._semaphore._value == 0
            assert rate_limiter._semaphore._value == 1

    # --- Tiered logging tests ---

    @pytest.mark.asyncio
    @patch("jira.rate_limiter.logger")
    async def test_log_rate_limit_status_debug_when_healthy(
        self, mock_logger: AsyncMock
    ) -> None:
        """Tests debug logging when rate limit is healthy."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "80",
                "x-ratelimit-reset": "2099-01-01T12:00:00Z",
            },
        )

        await rate_limiter.on_response(response)

        mock_logger.bind.return_value.debug.assert_called_once()
        call_args = str(mock_logger.bind.return_value.debug.call_args)
        assert "Status" in call_args

    @pytest.mark.asyncio
    @patch("jira.rate_limiter.logger")
    async def test_log_rate_limit_status_warning_when_near_exhaustion(
        self, mock_logger: AsyncMock
    ) -> None:
        """Tests warning logging when rate limit is near exhaustion (<= 10%)."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "5",
                "x-ratelimit-reset": "2099-01-01T12:00:00Z",
            },
        )

        await rate_limiter.on_response(response)

        mock_logger.bind.return_value.warning.assert_called_once()
        call_args = str(mock_logger.bind.return_value.warning.call_args)
        assert "Near exhaustion" in call_args

    @pytest.mark.asyncio
    @patch("jira.rate_limiter.logger")
    async def test_log_rate_limit_status_warning_when_exhausted(
        self, mock_logger: AsyncMock
    ) -> None:
        """Tests warning logging when rate limit is exhausted."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "2099-01-01T12:00:00Z",
            },
        )

        await rate_limiter.on_response(response)

        mock_logger.bind.return_value.warning.assert_called_once()
        call_args = str(mock_logger.bind.return_value.warning.call_args)
        assert "Exhausted" in call_args

    @pytest.mark.asyncio
    async def test_reset_time_parsing_with_different_iso_formats(self) -> None:
        """Tests reset time parsing with different ISO 8601 formats."""
        rate_limiter = JiraRateLimiter()

        # Test with Z suffix
        response_z = httpx.Response(
            200,
            headers={
                "x-ratelimit-reset": "2099-01-01T12:00:00Z",
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "50",
            },
        )

        await rate_limiter.on_response(response_z)
        expected_timestamp = datetime(
            2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc
        ).timestamp()
        assert rate_limiter._rate_limit_info is not None
        assert abs(rate_limiter._rate_limit_info.reset_time - expected_timestamp) < 0.01

        # Reset for next test
        rate_limiter._initialized = False
        rate_limiter._rate_limit_info = None

        # Test with +00:00 suffix
        response_offset = httpx.Response(
            200,
            headers={
                "x-ratelimit-reset": "2099-01-01T12:00:00+00:00",
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "50",
            },
        )

        await rate_limiter.on_response(response_offset)
        assert rate_limiter._rate_limit_info is not None
        assert abs(rate_limiter._rate_limit_info.reset_time - expected_timestamp) < 0.01

    @pytest.mark.asyncio
    async def test_on_response_initializes_from_partial_headers(self) -> None:
        """Tests that on_response initializes from limit + remaining without reset."""
        rate_limiter = JiraRateLimiter()

        response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "80",
            },
        )

        before = time.time()
        await rate_limiter.on_response(response)
        after = time.time()

        assert rate_limiter._initialized is True
        assert rate_limiter._rate_limit_info is not None
        assert rate_limiter._rate_limit_info.limit == 100
        assert rate_limiter._rate_limit_info.remaining == 80
        # reset_time should be synthesized ~DEFAULT_RATE_LIMIT_WINDOW_SECONDS from now
        expected_low = before + DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        expected_high = after + DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        assert expected_low <= rate_limiter._rate_limit_info.reset_time <= expected_high

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_throttle_from_partial_headers(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests that proactive throttling engages after init from partial headers."""
        rate_limiter = JiraRateLimiter(minimum_limit_remaining=5)

        # Simulate a normal response with low remaining, no reset header
        response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "3",
            },
        )

        await rate_limiter.on_response(response)
        assert rate_limiter._initialized is True

        # Now entering the context should trigger proactive sleep
        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration > 0

    @pytest.mark.asyncio
    async def test_on_response_syncs_remaining_upward(self) -> None:
        """Tests that on_response syncs remaining upward when server reports more."""
        rate_limiter = JiraRateLimiter()

        # Initialize with a response
        init_response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "350",
                "x-ratelimit-remaining": "340",
            },
        )
        await rate_limiter.on_response(init_response)
        assert rate_limiter._rate_limit_info is not None

        # Simulate internal counter being decremented (e.g., by _enforce_rate_limit)
        rate_limiter._rate_limit_info.remaining = 100

        # Server reports higher remaining (window reset server-side)
        fresh_response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "350",
                "x-ratelimit-remaining": "349",
            },
        )
        await rate_limiter.on_response(fresh_response)

        # Remaining should have been synced upward
        assert rate_limiter._rate_limit_info.remaining == 349

    @pytest.mark.asyncio
    async def test_on_response_does_not_sync_remaining_downward(self) -> None:
        """Tests that on_response does NOT reduce remaining from server headers."""
        rate_limiter = JiraRateLimiter()

        init_response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "350",
                "x-ratelimit-remaining": "340",
            },
        )
        await rate_limiter.on_response(init_response)
        assert rate_limiter._rate_limit_info is not None
        assert rate_limiter._rate_limit_info.remaining == 340

        # Server reports lower remaining — should NOT reduce our counter
        lower_response = httpx.Response(
            200,
            headers={
                "x-ratelimit-limit": "350",
                "x-ratelimit-remaining": "200",
            },
        )
        await rate_limiter.on_response(lower_response)

        # Remaining should stay at 340 (not reduced to 200)
        assert rate_limiter._rate_limit_info.remaining == 340
