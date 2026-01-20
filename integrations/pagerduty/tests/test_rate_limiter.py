import asyncio
from typing import Generator
from unittest.mock import Mock, patch

import httpx
import pytest

from clients.rate_limiter import PagerDutyRateLimiter, RateLimitInfo


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Mock, None, None]:
    with patch("asyncio.sleep") as m:
        yield m


class TestPagerDutyRateLimiter:
    @pytest.mark.asyncio
    async def test_update_rate_limits_success_sets_info(self, mock_sleep: Mock) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        headers = httpx.Headers(
            {
                "ratelimit-limit": "1000",
                "ratelimit-remaining": "999",
                "ratelimit-reset": "3600",
            }
        )

        info = limiter.update_rate_limits(headers, "/incidents/123")
        assert info is not None
        assert info.limit == 1000
        assert info.remaining == 999
        # 1 used out of 1000 => 0.1% utilization
        assert info.utilization_percentage == 0.1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_update_when_headers_missing(self, mock_sleep: Mock) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        headers = httpx.Headers({})  # missing required headers

        info = limiter.update_rate_limits(headers, "/incidents/123")
        assert info is None
        assert limiter.rate_limit_info is None
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_enters_pause_when_remaining_le_threshold(
        self, mock_sleep: Mock
    ) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=3)

        # Seed limiter with remaining == 15 (at threshold) and a short reset in the future
        reset_in = 5
        limiter.rate_limit_info = RateLimitInfo(
            limit=960, remaining=15, seconds_until_reset=reset_in
        )

        mock_sleep.reset_mock()
        async with limiter:
            # inside context - nothing to do
            pass

        assert mock_sleep.call_count >= 1
        assert any(args[0] >= reset_in for args, _ in mock_sleep.call_args_list)

    @pytest.mark.asyncio
    async def test_does_not_pause_when_remaining_above_threshold(
        self, mock_sleep: Mock
    ) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=3)

        # Seed limiter with remaining == 16 (above threshold of 15)
        limiter.rate_limit_info = RateLimitInfo(
            limit=960, remaining=16, seconds_until_reset=60
        )

        mock_sleep.reset_mock()
        async with limiter:
            # inside context - nothing to do
            pass

        # Should not sleep when remaining is above threshold
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_semaphore(
        self, mock_sleep: Mock
    ) -> None:
        max_concurrent = 4
        limiter = PagerDutyRateLimiter(max_concurrent=max_concurrent)

        concurrent = 0
        max_seen = 0

        async def worker(_: int) -> None:
            nonlocal concurrent, max_seen
            async with limiter:
                concurrent += 1
                max_seen = max(max_seen, concurrent)
                # simulate brief work
                await asyncio.sleep(0.01)
                concurrent -= 1

        tasks = [asyncio.create_task(worker(i)) for i in range(max_concurrent * 2)]
        await asyncio.gather(*tasks)

        assert max_seen <= max_concurrent
