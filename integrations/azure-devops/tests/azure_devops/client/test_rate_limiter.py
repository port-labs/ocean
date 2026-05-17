import asyncio
import time
from unittest.mock import AsyncMock, patch, create_autospec

import httpx
import pytest
from azure_devops.client.rate_limiter import (
    MAX_RETRY_AFTER_WAIT_SECONDS,
    MIN_REMAINING_BACKOFF_SECONDS,
    AzureDevOpsRateLimiter,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestAzureDevOpsRateLimiter:
    """Test suite for the AzureDevOpsRateLimiter."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_smoothing_wait_when_threshold_reached(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        The limiter applies a fixed smoothing delay (not a sleep-until-reset)
        when remaining is at the configured threshold.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining
        rate_limiter._reset_time = time.time() + 10.0

        response = create_autospec(httpx.Response, instance=True)
        response.status_code = 200
        mock_client.get.return_value = response

        async with rate_limiter:
            await mock_client.get("https://test.com")

        mock_sleep.assert_awaited_once_with(MIN_REMAINING_BACKOFF_SECONDS)

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_smoothing_wait_when_below_threshold(
        self, mock_sleep: AsyncMock, mock_client: AsyncMock
    ) -> None:
        """
        The limiter applies the fixed smoothing delay when remaining is below
        the configured threshold, irrespective of how far in the future the
        (counterfactual) reset time sits.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = time.time() + 600.0  # 10 minutes in future

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once_with(MIN_REMAINING_BACKOFF_SECONDS)

    async def test_update_from_headers_parses_headers_correctly(self) -> None:
        """
        update_from_headers correctly parses Azure DevOps headers and updates
        the limiter's state.
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
        """update_from_headers handles partial headers correctly."""
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
        """update_from_headers handles invalid header values gracefully."""
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
        """update_from_headers handles empty headers correctly."""
        headers: httpx.Headers = httpx.Headers({})

        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(headers)

        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_wait_when_remaining_above_threshold(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        The limiter does not sleep when remaining requests are above the
        threshold, even if the reset time is in the future or in the past.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining + 10
        rate_limiter._reset_time = time.time() + 600

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_no_wait_when_no_rate_limit_info(self, mock_sleep: AsyncMock) -> None:
        """
        The limiter does not sleep when no rate limit information has been
        received.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    async def test_concurrent_requests_are_limited_by_semaphore(self) -> None:
        """The semaphore correctly limits the number of concurrent requests."""
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
        """The rate limiter initializes with correct default values."""
        rate_limiter = AzureDevOpsRateLimiter()

        assert rate_limiter._minimum_limit_remaining == 1
        assert rate_limiter._semaphore._value == 15
        assert rate_limiter._limit is None
        assert rate_limiter._remaining is None
        assert rate_limiter._reset_time is None

    async def test_custom_initialization_values(self) -> None:
        """The rate limiter initializes with custom values correctly."""
        max_concurrent = 25
        minimum_limit_remaining = 10
        rate_limiter = AzureDevOpsRateLimiter(
            max_concurrent=max_concurrent,
            minimum_limit_remaining=minimum_limit_remaining,
        )

        assert rate_limiter._minimum_limit_remaining == minimum_limit_remaining
        assert rate_limiter._semaphore._value == max_concurrent

    async def test_seconds_until_reset_property(self) -> None:
        """seconds_until_reset (telemetry-only) computes correctly."""
        rate_limiter = AzureDevOpsRateLimiter()

        assert rate_limiter.seconds_until_reset == 0.0

        future_time = time.time() + 30
        rate_limiter._reset_time = future_time
        assert abs(rate_limiter.seconds_until_reset - 30.0) < 1.0

        past_time = time.time() - 30
        rate_limiter._reset_time = past_time
        assert rate_limiter.seconds_until_reset == 0.0

    async def test_context_manager_semaphore_release_on_exception(self) -> None:
        """The semaphore is released even when an exception occurs."""
        rate_limiter = AzureDevOpsRateLimiter(max_concurrent=5)
        initial_semaphore_value = rate_limiter._semaphore._value

        try:
            async with rate_limiter:
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert rate_limiter._semaphore._value == initial_semaphore_value

    async def test_multiple_header_updates(self) -> None:
        """Multiple header updates work correctly under the min() semantics."""
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
        # min(100, 50) = 50; lower values always win.
        assert rate_limiter._remaining == 50
        assert rate_limiter._reset_time is not None

    async def test_update_from_headers_uses_min_for_remaining_when_out_of_order(
        self,
    ) -> None:
        """
        Out-of-order responses must not silently re-inflate the budget: an
        older (higher) Remaining arriving after a fresher (lower) one is
        ignored in favour of the lower value.
        """
        rate_limiter = AzureDevOpsRateLimiter()

        await rate_limiter.update_from_headers(
            httpx.Headers(
                {
                    "X-RateLimit-Limit": "200",
                    "X-RateLimit-Remaining": "50",
                }
            )
        )
        assert rate_limiter._remaining == 50

        # Stale higher value lands afterwards — must NOT overwrite.
        await rate_limiter.update_from_headers(
            httpx.Headers(
                {
                    "X-RateLimit-Limit": "200",
                    "X-RateLimit-Remaining": "80",
                }
            )
        )
        assert rate_limiter._remaining == 50

    async def test_aenter_does_not_hold_lock_during_sleep(self) -> None:
        """
        With _remaining below threshold __aenter__ sleeps for the smoothing
        delay; concurrent update_from_headers must be able to complete during
        that window because the lock is released before the sleep starts.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1

        update_completed_at: list[float] = []

        async def update_during_sleep() -> None:
            # Give __aenter__ a moment to enter the smoothing sleep.
            await asyncio.sleep(MIN_REMAINING_BACKOFF_SECONDS / 5)
            await rate_limiter.update_from_headers(
                httpx.Headers(
                    {
                        "X-RateLimit-Limit": "200",
                        "X-RateLimit-Remaining": "1",
                    }
                )
            )
            update_completed_at.append(time.monotonic())

        async def enter_limiter() -> float:
            async with rate_limiter:
                pass
            return time.monotonic()

        update_task = asyncio.create_task(update_during_sleep())
        aenter_finished_at = await enter_limiter()
        await update_task

        # update_from_headers must finish before __aenter__ returns — proving
        # the lock was not held throughout the smoothing sleep.
        assert update_completed_at, "update_from_headers did not complete"
        assert update_completed_at[0] <= aenter_finished_at

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_header_triggers_bounded_wait(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        A Retry-After header recorded via update_from_headers gates the next
        __aenter__ for approximately the indicated duration.
        """
        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(httpx.Headers({"Retry-After": "2"}))

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once()
        slept_for = mock_sleep.call_args[0][0]
        assert 1.5 <= slept_for <= 2.0, f"expected ~2s, slept {slept_for}"

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_wait_is_clamped_to_max(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        A pathologically large Retry-After value (e.g. 600s) must be clamped
        to MAX_RETRY_AFTER_WAIT_SECONDS so the limiter cannot consume the 90s
        webhook processor budget.
        """
        rate_limiter = AzureDevOpsRateLimiter()
        await rate_limiter.update_from_headers(httpx.Headers({"Retry-After": "600"}))

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once_with(MAX_RETRY_AFTER_WAIT_SECONDS)

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_takes_precedence_over_smoothing(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        When both a Retry-After wait and the Remaining-threshold smoothing
        would apply, Retry-After wins (it's the explicit instruction from
        ADO; smoothing is a local heuristic).
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = 0  # would normally trigger smoothing
        await rate_limiter.update_from_headers(httpx.Headers({"Retry-After": "3"}))

        async with rate_limiter:
            pass

        mock_sleep.assert_awaited_once()
        slept_for = mock_sleep.call_args[0][0]
        # Retry-After (~3s), not the 0.25s smoothing delay.
        assert slept_for > MIN_REMAINING_BACKOFF_SECONDS

    async def test_retry_after_uses_max_for_overlapping_windows(self) -> None:
        """
        A stale shorter Retry-After arriving after a fresher longer one must
        not undercut the longer wait.
        """
        rate_limiter = AzureDevOpsRateLimiter()

        await rate_limiter.update_from_headers(httpx.Headers({"Retry-After": "5"}))
        long_until = rate_limiter._retry_after_until
        assert long_until is not None

        # A stale (shorter) Retry-After lands afterwards.
        await rate_limiter.update_from_headers(httpx.Headers({"Retry-After": "1"}))

        assert rate_limiter._retry_after_until == long_until

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retry_after_does_not_wait_when_already_expired(
        self, mock_sleep: AsyncMock
    ) -> None:
        """
        Once the Retry-After deadline has passed, no wait is applied — the
        deadline is allowed to expire naturally without explicit clearing.
        """
        rate_limiter = AzureDevOpsRateLimiter()
        # Simulate an already-elapsed Retry-After deadline.
        rate_limiter._retry_after_until = time.time() - 1.0

        async with rate_limiter:
            pass

        mock_sleep.assert_not_awaited()

    async def test_smoothing_delay_is_bounded(self) -> None:
        """
        Even with a Reset header that points 600s into the future, entering
        the limiter must finish within ~1s — proving the limiter never sleeps
        on Reset and the 90s webhook processor budget cannot be exhausted by
        the limiter alone.
        """
        rate_limiter = AzureDevOpsRateLimiter(minimum_limit_remaining=5)
        rate_limiter._remaining = rate_limiter._minimum_limit_remaining - 1
        rate_limiter._reset_time = time.time() + 600.0

        start = time.monotonic()
        async with rate_limiter:
            pass
        elapsed = time.monotonic() - start

        assert (
            elapsed < 1.0
        ), f"Limiter took {elapsed:.3f}s — Reset header should not gate sleeps"
