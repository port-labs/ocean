from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from clients.rate_limiter import PagerDutyRateLimiter
from clients.retry_transport import PagerDutyRetryTransport


def _build_transport(rate_limiter: PagerDutyRateLimiter) -> PagerDutyRetryTransport:
    return PagerDutyRetryTransport(
        rate_limiter=rate_limiter,
        wrapped_transport=MagicMock(spec=httpx.AsyncBaseTransport),
    )


class TestPagerDutyRetryTransport:
    @pytest.mark.asyncio
    async def test_after_retry_async_feeds_limiter_for_retryable_response(self) -> None:
        """Intermediate retry responses (e.g. per-minute 429s) feed the limiter
        early so concurrent in-flight calls can react before they exhaust their
        own retry budgets."""
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        request = httpx.Request(
            "GET", "https://api.pagerduty.com/analytics/raw/incidents/X"
        )
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = httpx.Headers(
            {
                "ratelimit-limit": "960",
                "ratelimit-remaining": "0",
                "ratelimit-reset": "56",
            }
        )

        await transport.after_retry_async(request, response, attempt=1)

        assert limiter.rate_limit_info is not None
        assert limiter.rate_limit_info.remaining == 0

    @pytest.mark.asyncio
    async def test_after_retry_async_skips_final_response(self) -> None:
        """Final responses (2xx, daily-exhausted 429) are not retried, so the
        transport leaves the limiter update to `send_api_request`'s finally."""
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        request = httpx.Request("GET", "https://api.pagerduty.com/services")
        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.headers = httpx.Headers(
            {
                "ratelimit-limit": "960",
                "ratelimit-remaining": "959",
                "ratelimit-reset": "56",
            }
        )

        await transport.after_retry_async(request, ok_response, attempt=1)

        assert limiter.rate_limit_info is None
        assert limiter.daily_rate_limit_info is None

    @pytest.mark.asyncio
    async def test_should_retry_async_false_for_429_with_daily_exhausted(self) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = httpx.Headers(
            {
                "ratelimit-remaining": "959",
                "daily-ratelimit-remaining": "-1",
                "daily-ratelimit-reset": "49015",
            }
        )

        assert await transport._should_retry_async(response) is False

    @pytest.mark.asyncio
    async def test_should_retry_async_true_for_regular_429(self) -> None:
        """A 429 without `daily-ratelimit-*` headers must still be retried by the parent."""
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = httpx.Headers(
            {
                "ratelimit-limit": "960",
                "ratelimit-remaining": "0",
                "ratelimit-reset": "56",
            }
        )

        assert await transport._should_retry_async(response) is True

    @pytest.mark.asyncio
    async def test_should_retry_async_true_for_429_with_daily_remaining(self) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = httpx.Headers(
            {
                "ratelimit-remaining": "0",
                "daily-ratelimit-remaining": "5",
                "daily-ratelimit-reset": "49015",
            }
        )

        assert await transport._should_retry_async(response) is True

    @pytest.mark.asyncio
    async def test_should_retry_async_false_for_2xx(self) -> None:
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.headers = httpx.Headers({})

        assert await transport._should_retry_async(response) is False

    @pytest.mark.asyncio
    async def test_daily_exhausted_429_does_not_loop(self) -> None:
        """End-to-end-ish: a 429 with daily quota gone must return on the first
        attempt rather than burning ~10 retries × ~60s."""
        limiter = PagerDutyRateLimiter(max_concurrent=5)
        transport = _build_transport(limiter)

        request = httpx.Request(
            "GET", "https://api.pagerduty.com/analytics/raw/incidents/X"
        )

        first_429 = MagicMock(spec=httpx.Response)
        first_429.status_code = 429
        first_429.headers = httpx.Headers(
            {
                "ratelimit-remaining": "959",
                "daily-ratelimit-remaining": "-1",
                "daily-ratelimit-reset": "49015",
            }
        )
        first_429.aclose = AsyncMock()
        first_429.aread = AsyncMock()

        send_method = AsyncMock(return_value=first_429)

        result = await transport._retry_operation_async(request, send_method)

        assert send_method.await_count == 1
        assert result is first_429
