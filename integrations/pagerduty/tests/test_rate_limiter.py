import asyncio
from typing import Generator
from unittest.mock import Mock, patch

import httpx
import pytest

from clients.rate_limiter import (
    PagerDutyDailyRateLimitExceededError,
    PagerDutyRateLimiter,
    RateLimitInfo,
)


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
    async def test_enters_pause_when_90_percent_used(self, mock_sleep: Mock) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=3)

        # 90% usage: 900 used, 100 remaining out of 1000
        reset_in = 5
        limiter.rate_limit_info = RateLimitInfo(
            limit=1000, remaining=100, seconds_until_reset=reset_in
        )

        mock_sleep.reset_mock()
        async with limiter:
            # inside context - nothing to do
            pass

        # Should sleep when at 90% utilization
        assert mock_sleep.call_count >= 1
        assert any(args[0] >= reset_in for args, _ in mock_sleep.call_args_list)

    @pytest.mark.asyncio
    async def test_no_pause_when_below_90_percent(self, mock_sleep: Mock) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=3)

        # 50% usage: 500 used, 500 remaining out of 1000
        limiter.rate_limit_info = RateLimitInfo(
            limit=1000, remaining=500, seconds_until_reset=60
        )

        mock_sleep.reset_mock()
        async with limiter:
            # inside context - nothing to do
            pass

        # Should not sleep when remaining is above threshold
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_headers_are_parsed_and_stored(self, mock_sleep: Mock) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        headers = httpx.Headers(
            {
                "ratelimit-limit": "960",
                "ratelimit-remaining": "959",
                "ratelimit-reset": "56",
                "daily-ratelimit-limit": "10",
                "daily-ratelimit-remaining": "5",
                "daily-ratelimit-reset": "49015",
            }
        )

        limiter.update_rate_limits(headers, "analytics/metrics/incidents/services")

        assert limiter.daily_rate_limit_info is not None
        assert limiter.daily_rate_limit_info.limit == 10
        assert limiter.daily_rate_limit_info.remaining == 5
        assert limiter.daily_rate_limit_info.seconds_until_reset == 49015
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_state_not_clobbered_by_rest_response(
        self, mock_sleep: Mock
    ) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        limiter.daily_rate_limit_info = RateLimitInfo(
            limit=10, remaining=2, seconds_until_reset=49000
        )
        headers = httpx.Headers(
            {
                "ratelimit-limit": "960",
                "ratelimit-remaining": "900",
                "ratelimit-reset": "30",
            }
        )

        limiter.update_rate_limits(headers, "services")

        assert limiter.daily_rate_limit_info.limit == 10
        assert limiter.daily_rate_limit_info.remaining == 2
        assert limiter.daily_rate_limit_info.seconds_until_reset == 49000
        assert limiter.rate_limit_info is not None
        assert limiter.rate_limit_info.remaining == 900
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_daily_budget_raises_for_analytics_when_exhausted(
        self, mock_sleep: Mock
    ) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        limiter.daily_rate_limit_info = RateLimitInfo(
            limit=10, remaining=-1, seconds_until_reset=49015
        )

        with pytest.raises(PagerDutyDailyRateLimitExceededError):
            limiter.check_daily_budget("analytics/metrics/incidents/services")

    @pytest.mark.asyncio
    async def test_check_daily_budget_no_op_for_rest_endpoint(
        self, mock_sleep: Mock
    ) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        limiter.daily_rate_limit_info = RateLimitInfo(
            limit=10, remaining=-1, seconds_until_reset=49015
        )

        # Must not raise — REST endpoints are not subject to the analytics daily quota
        limiter.check_daily_budget("services")

    @pytest.mark.asyncio
    async def test_check_daily_budget_no_op_when_daily_state_unknown(
        self, mock_sleep: Mock
    ) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)

        # Fresh limiter — no daily info observed yet, must not raise
        limiter.check_daily_budget("analytics/metrics/incidents/services")

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
