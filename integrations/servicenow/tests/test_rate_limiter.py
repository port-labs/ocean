import asyncio
import time
from typing import Generator
from unittest.mock import Mock, patch

import httpx
import pytest

from rate_limiter import ServiceNowRateLimiter


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Mock, None, None]:
    with patch("rate_limiter.asyncio.sleep") as m:
        yield m


class TestRateLimiterInit:
    def test_initial_state(self) -> None:
        limiter = ServiceNowRateLimiter()
        assert limiter._limit is None
        assert limiter._reset_time is None
        assert limiter._request_count == 0

    def test_seconds_until_reset_no_reset_time(self) -> None:
        limiter = ServiceNowRateLimiter()
        assert limiter.seconds_until_reset == 0.0

    def test_seconds_until_reset_future(self) -> None:
        limiter = ServiceNowRateLimiter()
        limiter._reset_time = time.time() + 60
        assert 59 <= limiter.seconds_until_reset <= 61

    def test_seconds_until_reset_past(self) -> None:
        limiter = ServiceNowRateLimiter()
        limiter._reset_time = time.time() - 10
        assert limiter.seconds_until_reset == 0.0


class TestRateLimiterAenter:
    @pytest.mark.asyncio
    async def test_no_limit_increments_count(self, mock_sleep: Mock) -> None:
        limiter = ServiceNowRateLimiter()
        async with limiter:
            pass
        assert limiter._request_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_limit_increments_count(self, mock_sleep: Mock) -> None:
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._reset_time = time.time() + 3600
        limiter._request_count = 50

        async with limiter:
            pass
        assert limiter._request_count == 51
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_at_limit_sleeps_and_retries(self, mock_sleep: Mock) -> None:
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._request_count = 100
        limiter._reset_time = time.time() + 10

        async with limiter:
            pass

        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert delay >= 9

    @pytest.mark.asyncio
    async def test_at_limit_no_reset_time_passes_through(
        self, mock_sleep: Mock
    ) -> None:
        """If limit is reached but no reset_time, don't block."""
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._request_count = 100
        limiter._reset_time = None

        async with limiter:
            pass
        assert limiter._request_count == 101
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_window_resets_count(self, mock_sleep: Mock) -> None:
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._request_count = 100
        limiter._reset_time = time.time() - 1

        async with limiter:
            pass
        assert limiter._request_count == 1
        assert limiter._reset_time is None
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_sleep_with_window_expired_during_sleep(
        self, mock_sleep: Mock
    ) -> None:
        """If the window expires during sleep, counters reset on re-evaluation."""
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._request_count = 100
        limiter._reset_time = time.time() + 5

        async def simulate_time_passing(*args: object) -> None:
            limiter._reset_time = time.time() - 1

        mock_sleep.side_effect = simulate_time_passing

        async with limiter:
            pass

        assert limiter._request_count == 1
        assert limiter._reset_time is None
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_requests_increment_sequentially(
        self, mock_sleep: Mock
    ) -> None:
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._reset_time = time.time() + 3600

        for _ in range(5):
            async with limiter:
                pass

        assert limiter._request_count == 5
        mock_sleep.assert_not_called()


class TestUpdateFromHeaders:
    @pytest.mark.asyncio
    async def test_parses_limit_header(self) -> None:
        limiter = ServiceNowRateLimiter()
        headers = httpx.Headers({"x-ratelimit-limit": "500"})
        await limiter.update_from_headers(headers)
        assert limiter._limit == 500

    @pytest.mark.asyncio
    async def test_parses_reset_header(self) -> None:
        limiter = ServiceNowRateLimiter()
        reset_time = time.time() + 3600
        headers = httpx.Headers({"x-ratelimit-reset": str(reset_time)})
        await limiter.update_from_headers(headers)
        assert limiter._reset_time == reset_time

    @pytest.mark.asyncio
    async def test_parses_both_headers(self) -> None:
        limiter = ServiceNowRateLimiter()
        reset_time = time.time() + 3600
        headers = httpx.Headers(
            {"x-ratelimit-limit": "1000", "x-ratelimit-reset": str(reset_time)}
        )
        await limiter.update_from_headers(headers)
        assert limiter._limit == 1000
        assert limiter._reset_time == reset_time

    @pytest.mark.asyncio
    async def test_retry_after_sets_reset_time_when_none(self) -> None:
        limiter = ServiceNowRateLimiter()
        headers = httpx.Headers({"retry-after": "30"})
        before = time.time()
        await limiter.update_from_headers(headers)
        assert limiter._reset_time is not None
        assert limiter._reset_time >= before + 29

    @pytest.mark.asyncio
    async def test_retry_after_uses_max_with_existing_reset(self) -> None:
        """Retry-After should not overwrite a later X-RateLimit-Reset."""
        limiter = ServiceNowRateLimiter()
        far_future = time.time() + 7200
        headers = httpx.Headers(
            {
                "x-ratelimit-limit": "100",
                "x-ratelimit-reset": str(far_future),
                "retry-after": "30",
            }
        )
        await limiter.update_from_headers(headers)
        assert limiter._reset_time == far_future

    @pytest.mark.asyncio
    async def test_retry_after_wins_when_later_than_reset(self) -> None:
        """Retry-After wins if it computes to a later time than X-RateLimit-Reset."""
        limiter = ServiceNowRateLimiter()
        near_future = time.time() + 5
        headers = httpx.Headers(
            {
                "x-ratelimit-limit": "100",
                "x-ratelimit-reset": str(near_future),
                "retry-after": "120",
            }
        )
        before = time.time()
        await limiter.update_from_headers(headers)
        assert limiter._reset_time is not None
        assert limiter._reset_time >= before + 119

    @pytest.mark.asyncio
    async def test_exhausted_reset_header_is_ignored(self) -> None:
        """A reset timestamp already in the past should not be set."""
        limiter = ServiceNowRateLimiter()
        headers = httpx.Headers({"x-ratelimit-reset": str(time.time() - 60)})
        await limiter.update_from_headers(headers)
        assert limiter._reset_time is None

    @pytest.mark.asyncio
    async def test_no_headers_is_noop(self) -> None:
        limiter = ServiceNowRateLimiter()
        headers = httpx.Headers({})
        await limiter.update_from_headers(headers)
        assert limiter._limit is None
        assert limiter._reset_time is None

    @pytest.mark.asyncio
    async def test_invalid_header_values_logged_not_raised(self) -> None:
        limiter = ServiceNowRateLimiter()
        headers = httpx.Headers({"x-ratelimit-limit": "not-a-number"})
        await limiter.update_from_headers(headers)
        assert limiter._limit is None

    @pytest.mark.asyncio
    async def test_does_not_reset_request_count(self) -> None:
        """update_from_headers should never touch _request_count."""
        limiter = ServiceNowRateLimiter()
        limiter._request_count = 42
        headers = httpx.Headers(
            {
                "x-ratelimit-limit": "100",
                "x-ratelimit-reset": str(time.time() + 3600),
            }
        )
        await limiter.update_from_headers(headers)
        assert limiter._request_count == 42


class TestRateLimiterConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_enters_all_increment(self, mock_sleep: Mock) -> None:
        """Multiple concurrent __aenter__ calls should each increment the count."""
        limiter = ServiceNowRateLimiter()
        limiter._limit = 100
        limiter._reset_time = time.time() + 3600

        async def enter_limiter() -> None:
            async with limiter:
                await asyncio.sleep(0)

        tasks = [asyncio.create_task(enter_limiter()) for _ in range(10)]
        await asyncio.gather(*tasks)

        assert limiter._request_count == 10
