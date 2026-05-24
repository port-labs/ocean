import asyncio
import time
from typing import Generator
from unittest.mock import AsyncMock, Mock, patch, create_autospec

import httpx
import pytest
from azure_devops.client.rate_limiter import (
    AzureDevOpsRateLimiter,
    _RATE_LIMIT_USAGE_THRESHOLD,
)
from port_ocean.context.event import EventType


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_event() -> Generator[Mock, None, None]:
    """The limiter reads ``event.event_type`` inside ``_should_sleep``.

    Patching the limiter's bound ``event`` avoids needing a real
    port_ocean event context stack. Defaults to RESYNC; tests that need
    a different event type can mutate ``mock_event.event_type``.
    """
    mock = Mock()
    mock.event_type = EventType.RESYNC
    with patch("azure_devops.client.rate_limiter.event", mock):
        yield mock


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestAzureDevOpsRateLimiter:
    """Test suite for the AzureDevOpsRateLimiter."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_resync_sleeps_when_utilization_at_threshold(
        self,
        mock_sleep: AsyncMock,
        mock_client: AsyncMock,
    ) -> None:
        """RESYNC: sleeps when utilization reaches the 95% threshold."""
        reset_time = time.time() + 10.0
        rate_limiter = AzureDevOpsRateLimiter()

        # 95% utilization: 1000 limit, 50 remaining
        rate_limiter._limit = 1000
        rate_limiter._remaining = 50
        rate_limiter._reset_time = reset_time

        response = create_autospec(httpx.Response, instance=True)
        response.status_code = 200
        mock_client.get.return_value = response

        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:
                await mock_client.get("https://test.com")

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 10.0) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_resync_sleeps_when_utilization_above_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """RESYNC: sleeps when utilization is above the 95% threshold."""
        reset_time = time.time() + 15.0
        rate_limiter = AzureDevOpsRateLimiter()

        # 99% utilization
        rate_limiter._limit = 1000
        rate_limiter._remaining = 10
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 15.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 15.0) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_resync_does_not_sleep_below_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """RESYNC: does not sleep when utilization is below the 95% threshold."""
        reset_time = time.time() + 20.0
        rate_limiter = AzureDevOpsRateLimiter()

        # 90% utilization — below threshold
        rate_limiter._limit = 1000
        rate_limiter._remaining = 100
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 20.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_non_resync_sleeps_when_remaining_at_critical_floor(
        self, mock_sleep: AsyncMock, mock_event: Mock
    ) -> None:
        """Non-RESYNC: sleeps only when remaining requests fall to <= 1."""
        mock_event.event_type = EventType.HTTP_REQUEST
        reset_time = time.time() + 25.0
        rate_limiter = AzureDevOpsRateLimiter()

        rate_limiter._limit = 1000
        rate_limiter._remaining = 1
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 25.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_awaited_once()
        calculated_sleep_duration = mock_sleep.call_args[0][0]
        assert abs(calculated_sleep_duration - 25.0) < 0.01

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_non_resync_does_not_sleep_above_critical_floor(
        self, mock_sleep: AsyncMock, mock_event: Mock
    ) -> None:
        """Non-RESYNC: does not sleep even at high utilization if remaining > 1."""
        mock_event.event_type = EventType.HTTP_REQUEST
        reset_time = time.time() + 10.0
        rate_limiter = AzureDevOpsRateLimiter()

        # 99% utilization but remaining (10) is still > 1
        rate_limiter._limit = 1000
        rate_limiter._remaining = 10
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_path_respects_event_type_gate(
        self,
        mock_sleep: AsyncMock,
        mock_event: Mock,
    ) -> None:
        """The retry-after sleep path also defers to the event-type gate.

        A non-RESYNC caller with remaining > 1 should not block on a stale
        reset_time alone.
        """
        mock_event.event_type = EventType.HTTP_REQUEST
        reset_time = time.time() + 20.0
        rate_limiter = AzureDevOpsRateLimiter()

        rate_limiter._limit = 1000
        rate_limiter._remaining = 50
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 20.0):
            async with rate_limiter:
                pass

        mock_sleep.assert_not_awaited()

    async def test_update_from_headers_parses_headers_correctly(self) -> None:
        """update_from_headers correctly parses Azure DevOps headers."""
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
        headers: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "200",
                # Missing X-RateLimit-Remaining
                "X-RateLimit-Reset": str(time.time() + 60),
            }
        )

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is not None

    async def test_update_from_headers_with_invalid_values(self) -> None:
        headers: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "invalid",
                "X-RateLimit-Remaining": "also_invalid",
                "X-RateLimit-Reset": "not_a_number",
            }
        )

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    async def test_update_from_headers_with_empty_headers(self) -> None:
        headers: httpx.Headers = httpx.Headers({})

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_proactive_wait_is_skipped_if_reset_in_past(
        self, mock_sleep: AsyncMock, mock_event: Mock
    ) -> None:
        """No sleep if the reset time is in the past."""
        mock_event.event_type = EventType.HTTP_REQUEST
        rate_limiter = AzureDevOpsRateLimiter()
        rate_limiter._limit = 1000
        rate_limiter._remaining = 1
        rate_limiter._reset_time = time.time() - 60

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_wait_when_no_rate_limit_info(self, mock_sleep: AsyncMock) -> None:
        """No sleep when no rate limit information has been received."""
        rate_limiter = AzureDevOpsRateLimiter()

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    async def test_concurrent_requests_are_limited_by_semaphore(self) -> None:
        concurrent_limit = 10
        rate_limiter = AzureDevOpsRateLimiter(max_concurrent=concurrent_limit)

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

    async def test_default_initialization_values(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()

        assert rate_limiter._minimum_limit_remaining == 1
        assert rate_limiter._semaphore._value == 15  # Default max_concurrent
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    async def test_custom_initialization_values(self) -> None:
        max_concurrent = 25
        minimum_limit_remaining = 10
        rate_limiter = AzureDevOpsRateLimiter(
            max_concurrent=max_concurrent,
            minimum_limit_remaining=minimum_limit_remaining,
        )

        assert rate_limiter._minimum_limit_remaining == minimum_limit_remaining
        assert rate_limiter._semaphore._value == max_concurrent

    async def test_seconds_until_reset_property(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()

        assert rate_limiter.seconds_until_reset == 0.0

        future_time = time.time() + 30
        rate_limiter._reset_time = future_time
        assert abs(rate_limiter.seconds_until_reset - 30.0) < 1.0

        past_time = time.time() - 30
        rate_limiter._reset_time = past_time
        assert rate_limiter.seconds_until_reset == 0.0

    async def test_utilization_property_with_no_state(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()
        assert rate_limiter.utilization == 0.0
        assert rate_limiter.is_utilization_threshold_exceeded is False

    async def test_utilization_property_calculations(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()
        rate_limiter._limit = 200
        rate_limiter._remaining = 50
        # used 150 of 200 → 0.75
        assert abs(rate_limiter.utilization - 0.75) < 1e-9
        assert rate_limiter.is_utilization_threshold_exceeded is False

        rate_limiter._remaining = 10
        # used 190 of 200 → 0.95
        assert abs(rate_limiter.utilization - 0.95) < 1e-9
        assert rate_limiter.is_utilization_threshold_exceeded is True

        rate_limiter._remaining = 5
        # used 195 of 200 → 0.975
        assert rate_limiter.utilization > _RATE_LIMIT_USAGE_THRESHOLD
        assert rate_limiter.is_utilization_threshold_exceeded is True

    async def test_utilization_property_with_zero_limit(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()
        rate_limiter._limit = 0
        rate_limiter._remaining = 0
        assert rate_limiter.utilization == 0.0

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_state_reset_after_resync_threshold_sleep(
        self, mock_sleep: AsyncMock
    ) -> None:
        """RESYNC: rate limit state is reset after proactive waiting."""
        reset_time = time.time() + 10.0
        rate_limiter = AzureDevOpsRateLimiter()

        rate_limiter._limit = 1000
        rate_limiter._remaining = 10  # 99% utilization
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 10.0):
            async with rate_limiter:
                pass

        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None
        mock_sleep.assert_awaited_once()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_state_reset_after_non_resync_critical_floor_sleep(
        self, mock_sleep: AsyncMock, mock_event: Mock
    ) -> None:
        """Non-RESYNC: state cleared after sleeping at the critical floor."""
        mock_event.event_type = EventType.HTTP_REQUEST
        reset_time = time.time() + 5.0
        rate_limiter = AzureDevOpsRateLimiter()

        rate_limiter._limit = 1000
        rate_limiter._remaining = 1
        rate_limiter._reset_time = reset_time

        with patch("time.time", return_value=reset_time - 5.0):
            async with rate_limiter:
                pass

        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None
        mock_sleep.assert_awaited_once()

    async def test_context_manager_semaphore_release_on_exception(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter(max_concurrent=5)
        initial_semaphore_value = rate_limiter._semaphore._value

        try:
            async with rate_limiter:
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert rate_limiter._semaphore._value == initial_semaphore_value

    async def test_multiple_header_updates(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()

        headers1: httpx.Headers = httpx.Headers(
            {
                "X-RateLimit-Limit": "200",
                "X-RateLimit-Remaining": "100",
            }
        )
        await rate_limiter.update_from_headers(headers1)
        assert rate_limiter._limit == 200
        assert rate_limiter._remaining == 100

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
