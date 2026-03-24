import asyncio
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from jira.rate_limiter import JiraRateLimiter, JiraRateLimitInfo
from jira.retry_transport import JiraRetryTransport


def _make_transport(
    notifier: AsyncMock | None = None,
) -> JiraRetryTransport:
    """Build a JiraRetryTransport with a no-op sync wrapped transport."""
    wrapped = httpx.MockTransport(handler=lambda r: httpx.Response(200))
    return JiraRetryTransport(
        wrapped_transport=wrapped,
        rate_limit_notifier=notifier,
    )


def _rate_limit_429_response() -> httpx.Response:
    req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")
    return httpx.Response(
        429,
        request=req,
        headers={
            "x-ratelimit-limit": "100",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "2099-01-01T12:00:00Z",
            "retry-after": "30",
        },
    )


def _normal_200_response() -> httpx.Response:
    req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")
    return httpx.Response(
        200,
        request=req,
        headers={
            "x-ratelimit-limit": "100",
            "x-ratelimit-remaining": "80",
        },
    )


def _plain_500_response() -> httpx.Response:
    req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")
    return httpx.Response(500, request=req, headers={})


class TestJiraRetryTransportAfterRetryAsync:
    @pytest.mark.asyncio
    async def test_calls_notifier_on_429(self) -> None:
        """Notifier is awaited when the response is a 429."""
        notifier = AsyncMock()
        transport = _make_transport(notifier=notifier)
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        await transport.after_retry_async(req, _rate_limit_429_response(), 1)

        notifier.assert_awaited_once()
        assert notifier.call_args.args[0].status_code == 429

    @pytest.mark.asyncio
    async def test_does_not_call_notifier_on_200(self) -> None:
        """Notifier is NOT called for a normal 200 response."""
        notifier = AsyncMock()
        transport = _make_transport(notifier=notifier)
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        await transport.after_retry_async(req, _normal_200_response(), 1)

        notifier.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_call_notifier_on_500(self) -> None:
        """Notifier is NOT called for a 500 error."""
        notifier = AsyncMock()
        transport = _make_transport(notifier=notifier)
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        await transport.after_retry_async(req, _plain_500_response(), 1)

        notifier.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_notifier_configured(self) -> None:
        """No error when rate_limit_notifier is None and a 429 is received."""
        transport = _make_transport(notifier=None)
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        # Should not raise
        await transport.after_retry_async(req, _rate_limit_429_response(), 1)


class TestAfterRetryAsyncWithRealRateLimiter:
    """Integration tests: after_retry_async wired to a real JiraRateLimiter."""

    @pytest.mark.asyncio
    async def test_429_notifies_rate_limiter_and_updates_state(self) -> None:
        """after_retry_async calling on_response updates the rate limiter state."""
        rate_limiter = JiraRateLimiter(max_concurrent=5)
        transport = JiraRetryTransport(
            wrapped_transport=httpx.MockTransport(handler=lambda r: httpx.Response(200)),
            rate_limit_notifier=rate_limiter.on_response,
        )
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        assert not rate_limiter._initialized

        await transport.after_retry_async(req, _rate_limit_429_response(), 1)

        assert rate_limiter._initialized
        assert rate_limiter._rate_limit_info is not None
        assert rate_limiter._rate_limit_info.remaining == 0
        assert rate_limiter._retry_after == 30.0

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_429_notification_causes_proactive_gating(
        self, mock_sleep: AsyncMock
    ) -> None:
        """After a 429 notification, subsequent context entries sleep proactively."""
        rate_limiter = JiraRateLimiter(max_concurrent=5, minimum_limit_remaining=1)
        transport = JiraRetryTransport(
            wrapped_transport=httpx.MockTransport(handler=lambda r: httpx.Response(200)),
            rate_limit_notifier=rate_limiter.on_response,
        )
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        # Simulate the transport notifying the rate limiter of a 429
        await transport.after_retry_async(req, _rate_limit_429_response(), 1)

        # Now a new request entering the context should be proactively gated
        async with rate_limiter:
            pass

        # The rate limiter should have slept due to retry_after=30
        mock_sleep.assert_awaited_once_with(30.0)

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_concurrent_requests_gated_after_429_notification(
        self, mock_sleep: AsyncMock
    ) -> None:
        """Multiple concurrent context entries are all gated after a 429 notification."""
        rate_limiter = JiraRateLimiter(max_concurrent=3, minimum_limit_remaining=1)
        transport = JiraRetryTransport(
            wrapped_transport=httpx.MockTransport(handler=lambda r: httpx.Response(200)),
            rate_limit_notifier=rate_limiter.on_response,
        )
        req = httpx.Request("GET", "https://test.atlassian.net/rest/api/3/issue")

        # Simulate 429 notification from transport
        await transport.after_retry_async(req, _rate_limit_429_response(), 1)

        entered_count = 0

        async def worker() -> None:
            nonlocal entered_count
            async with rate_limiter:
                entered_count += 1

        # Fire 3 concurrent workers — all should be gated
        await asyncio.gather(worker(), worker(), worker())

        assert entered_count == 3
        # sleep should have been called (at least once for the retry_after,
        # and subsequent entries should see the reset window)
        assert mock_sleep.await_count >= 1
