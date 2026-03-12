import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from clients.rate_limiter import AikidoRateLimiter, DEFAULT_MIN_REQUEST_INTERVAL


class TestAikidoRateLimiter:
    """Test suite for the AikidoRateLimiter."""

    def test_initialization_sets_default_values(self) -> None:
        """Tests that AikidoRateLimiter initializes with correct default values."""
        rate_limiter = AikidoRateLimiter()

        assert rate_limiter.min_interval == DEFAULT_MIN_REQUEST_INTERVAL
        assert rate_limiter._last_request_time == 0.0

    def test_initialization_with_custom_values(self) -> None:
        """Tests that AikidoRateLimiter initializes with custom min_interval."""
        rate_limiter = AikidoRateLimiter(min_interval=2.0)

        assert rate_limiter.min_interval == 2.0
        assert rate_limiter._last_request_time == 0.0

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_waits_when_interval_not_elapsed(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests that acquire() waits when minimum interval has not elapsed."""
        rate_limiter = AikidoRateLimiter(min_interval=4.0)

        current_time = time.monotonic()
        rate_limiter._last_request_time = current_time - 1.0

        with patch("time.monotonic", return_value=current_time):
            await rate_limiter.acquire()

        mock_sleep.assert_awaited_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert abs(sleep_duration - 3.0) < 0.01

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_no_wait_when_interval_elapsed(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests that acquire() does not wait when minimum interval has elapsed."""
        rate_limiter = AikidoRateLimiter(min_interval=4.0)

        current_time = time.monotonic()
        rate_limiter._last_request_time = current_time - 10.0

        with patch("time.monotonic", return_value=current_time):
            await rate_limiter.acquire()

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_no_wait_on_first_request(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests that first request (last_request_time=0) does not wait."""
        rate_limiter = AikidoRateLimiter(min_interval=4.0)

        assert rate_limiter._last_request_time == 0.0

        await rate_limiter.acquire()

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_context_manager_calls_acquire(self, mock_sleep: AsyncMock) -> None:
        """Tests that context manager entry calls acquire()."""
        rate_limiter = AikidoRateLimiter(min_interval=4.0)

        current_time = time.monotonic()
        rate_limiter._last_request_time = current_time - 1.0

        with patch("time.monotonic", return_value=current_time):
            async with rate_limiter:
                pass

        mock_sleep.assert_awaited_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert abs(sleep_duration - 3.0) < 0.01

    @pytest.mark.asyncio
    async def test_context_manager_returns_self(self) -> None:
        """Tests that context manager returns the rate limiter instance."""
        rate_limiter = AikidoRateLimiter()

        async with rate_limiter as limiter:
            assert limiter is rate_limiter

    @pytest.mark.asyncio
    async def test_context_manager_handles_exception(self) -> None:
        """Tests that context manager exits cleanly on exception."""
        rate_limiter = AikidoRateLimiter()

        with pytest.raises(ValueError, match="Test exception"):
            async with rate_limiter:
                raise ValueError("Test exception")

        async with rate_limiter:
            pass

    @pytest.mark.asyncio
    async def test_multiple_sequential_acquires(self) -> None:
        """Tests that multiple sequential acquires work correctly."""
        rate_limiter = AikidoRateLimiter(min_interval=0.01)

        for _ in range(3):
            async with rate_limiter:
                pass

    @pytest.mark.asyncio
    async def test_concurrent_requests_are_serialized(self) -> None:
        """Tests that concurrent requests are serialized by the lock."""
        rate_limiter = AikidoRateLimiter(min_interval=0.05)

        execution_order: list[int] = []
        lock = asyncio.Lock()

        async def worker(worker_id: int) -> None:
            async with rate_limiter:
                async with lock:
                    execution_order.append(worker_id)
                await asyncio.sleep(0.01)

        tasks = [asyncio.create_task(worker(i)) for i in range(3)]
        await asyncio.gather(*tasks)

        assert len(execution_order) == 3
        assert set(execution_order) == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_updates_last_request_time_after_acquire(self) -> None:
        """Tests that _last_request_time is updated after acquire()."""
        rate_limiter = AikidoRateLimiter()

        initial_time = rate_limiter._last_request_time
        assert initial_time == 0.0

        await rate_limiter.acquire()

        assert rate_limiter._last_request_time > initial_time

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_acquire_calculates_wait_time_correctly(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Tests that wait time is calculated as min_interval - elapsed."""
        rate_limiter = AikidoRateLimiter(min_interval=5.0)

        test_cases = [
            (1.0, 4.0),
            (2.5, 2.5),
            (4.9, 0.1),
        ]

        for elapsed, expected_wait in test_cases:
            mock_sleep.reset_mock()
            current_time = 100.0
            rate_limiter._last_request_time = current_time - elapsed

            with patch("time.monotonic", return_value=current_time):
                await rate_limiter.acquire()

            mock_sleep.assert_awaited_once()
            actual_wait = mock_sleep.call_args[0][0]
            assert (
                abs(actual_wait - expected_wait) < 0.01
            ), f"For elapsed={elapsed}, expected wait={expected_wait}, got {actual_wait}"
