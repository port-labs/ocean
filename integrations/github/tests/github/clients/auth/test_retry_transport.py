import time
from typing import Any, Callable, Coroutine, Optional
from unittest.mock import Mock, patch, AsyncMock

import httpx
import pytest

from github.clients.auth.retry_transport import GitHubRetryTransport


def _make_transport(
    notifier: Optional[AsyncMock] = None,
    token_refresher: Optional[Callable[[], Coroutine[Any, Any, dict[str, str]]]] = None,
) -> GitHubRetryTransport:
    """Build a GitHubRetryTransport with a no-op sync wrapped transport."""
    wrapped = httpx.MockTransport(handler=lambda r: httpx.Response(200))
    return GitHubRetryTransport(
        wrapped_transport=wrapped,
        rate_limit_notifier=notifier,
        token_refresher=token_refresher,
    )


def _rate_limit_429_response() -> httpx.Response:
    req = httpx.Request("GET", "https://api.github.com/repos")
    return httpx.Response(
        429,
        request=req,
        headers={
            "x-ratelimit-limit": "1000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) + 60),
            "retry-after": "60",
        },
    )


def _rate_limit_403_response() -> httpx.Response:
    req = httpx.Request("GET", "https://api.github.com/repos")
    return httpx.Response(
        403,
        request=req,
        headers={
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) + 3600),
        },
    )


def _plain_500_response() -> httpx.Response:
    req = httpx.Request("GET", "https://api.github.com/repos")
    return httpx.Response(500, request=req, headers={})


class TestGitHubRetryTransportAfterRetryAsync:
    @pytest.mark.asyncio
    async def test_calls_notifier_on_429(self) -> None:
        """Notifier is awaited when the response is a 429."""
        notifier = AsyncMock()
        transport = _make_transport(notifier=notifier)
        req = httpx.Request("GET", "https://api.github.com/test")

        await transport.after_retry_async(req, _rate_limit_429_response(), 1)

        notifier.assert_awaited_once()
        assert notifier.call_args.args[0].status_code == 429

    @pytest.mark.asyncio
    async def test_calls_notifier_on_rate_limit_403(self) -> None:
        """Notifier is awaited when the response is a 403 with exhausted rate limit headers."""
        notifier = AsyncMock()
        transport = _make_transport(notifier=notifier)
        req = httpx.Request("GET", "https://api.github.com/test")

        await transport.after_retry_async(req, _rate_limit_403_response(), 1)

        notifier.assert_awaited_once()
        assert notifier.call_args.args[0].status_code == 403

    @pytest.mark.asyncio
    async def test_does_not_call_notifier_on_non_rate_limit_response(self) -> None:
        """Notifier is NOT invoked for a plain 500 response."""
        notifier = AsyncMock()
        transport = _make_transport(notifier=notifier)
        req = httpx.Request("GET", "https://api.github.com/test")

        await transport.after_retry_async(req, _plain_500_response(), 1)

        notifier.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_notifier_does_not_raise(self) -> None:
        """When no notifier is configured, after_retry_async completes without error."""
        transport = _make_transport(notifier=None)
        req = httpx.Request("GET", "https://api.github.com/test")

        await transport.after_retry_async(req, _rate_limit_429_response(), 1)


class TestGitHubRetryTransportLogBeforeRetry:
    def test_logs_structured_fields_on_rate_limit_response(self) -> None:
        """logger.bind is called with rate limit context fields when a rate limit is hit."""
        transport = _make_transport()
        req = httpx.Request("GET", "https://api.github.com/test")
        response = _rate_limit_429_response()

        with (
            patch("github.clients.auth.retry_transport.logger") as mock_logger,
            patch.object(
                type(transport).__mro__[1], "_log_before_retry", return_value=None
            ),
        ):
            mock_bound = Mock()
            mock_logger.bind.return_value = mock_bound

            transport._log_before_retry(req, 10.0, response, None)

            mock_logger.bind.assert_called_once()
            call_kwargs = mock_logger.bind.call_args.kwargs
            assert call_kwargs["method"] == "GET"
            assert "remaining" in call_kwargs
            assert "limit" in call_kwargs
            assert "reset" in call_kwargs
            assert call_kwargs["sleep_time"] == 10.0
            mock_bound.warning.assert_called_once()

    def test_does_not_log_structured_fields_on_non_rate_limit_response(self) -> None:
        """logger.bind is NOT called for non-rate-limit responses."""
        transport = _make_transport()
        req = httpx.Request("GET", "https://api.github.com/test")

        with (
            patch("github.clients.auth.retry_transport.logger") as mock_logger,
            patch.object(
                type(transport).__mro__[1], "_log_before_retry", return_value=None
            ),
        ):
            transport._log_before_retry(req, 5.0, _plain_500_response(), None)

            mock_logger.bind.assert_not_called()


class TestGitHubRetryTransportShouldRetry:
    def test_should_retry_on_429(self) -> None:
        """_should_retry returns True for a 429 response."""
        transport = _make_transport()
        assert transport._should_retry(_rate_limit_429_response()) is True

    def test_should_retry_on_rate_limit_403(self) -> None:
        """_should_retry returns True for a 403 with exhausted rate limit headers."""
        transport = _make_transport()
        assert transport._should_retry(_rate_limit_403_response()) is True

    def test_should_not_retry_on_plain_403(self) -> None:
        """_should_retry returns False for a plain 403 (no exhausted headers) unless super does."""
        transport = _make_transport()
        req = httpx.Request("GET", "https://api.github.com/test")
        plain_403 = httpx.Response(403, request=req, headers={})

        with patch.object(
            type(transport).__mro__[1], "_should_retry", return_value=False
        ):
            assert transport._should_retry(plain_403) is False

    @pytest.mark.asyncio
    async def test_should_retry_async_on_429(self) -> None:
        """_should_retry_async returns True for a 429 response."""
        transport = _make_transport()

        with patch.object(
            type(transport).__mro__[1],
            "_should_retry_async",
            new=AsyncMock(return_value=False),
        ):
            result = await transport._should_retry_async(_rate_limit_429_response())

        assert result is True

    @pytest.mark.asyncio
    async def test_should_retry_async_on_rate_limit_403(self) -> None:
        """_should_retry_async returns True for a 403 with exhausted rate limit headers."""
        transport = _make_transport()

        with patch.object(
            type(transport).__mro__[1],
            "_should_retry_async",
            new=AsyncMock(return_value=False),
        ):
            result = await transport._should_retry_async(_rate_limit_403_response())

        assert result is True


class TestGitHubRetryTransportBeforeRetryAsync:
    @pytest.mark.asyncio
    async def test_returns_request_with_fresh_headers(self) -> None:
        """before_retry_async replaces auth headers using the token_refresher result."""
        fresh_headers = {
            "Authorization": "Bearer new-token",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        refresher = AsyncMock(return_value=fresh_headers)
        transport = _make_transport(token_refresher=refresher)

        original_req = httpx.Request(
            "GET",
            "https://api.github.com/repos",
            headers={"Authorization": "Bearer old-token"},
        )
        result = await transport.before_retry_async(original_req, None, 30.0, 1)

        assert result is not None
        refresher.assert_awaited_once()
        assert result.headers["Authorization"] == "Bearer new-token"
        assert result.method == original_req.method
        assert result.url == original_req.url

    @pytest.mark.asyncio
    async def test_returns_none_when_no_refresher(self) -> None:
        """before_retry_async returns None (use original request) when no token_refresher is set."""
        transport = _make_transport(token_refresher=None)
        req = httpx.Request("GET", "https://api.github.com/repos")

        result = await transport.before_retry_async(req, None, 30.0, 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_preserves_non_auth_headers(self) -> None:
        """before_retry_async keeps existing non-auth headers and only overlays fresh ones."""
        fresh_headers = {"Authorization": "Bearer new-token"}
        refresher = AsyncMock(return_value=fresh_headers)
        transport = _make_transport(token_refresher=refresher)

        original_req = httpx.Request(
            "GET",
            "https://api.github.com/repos",
            headers={
                "Authorization": "Bearer old-token",
                "X-Custom-Header": "keep-me",
            },
        )
        result = await transport.before_retry_async(original_req, None, 30.0, 1)

        assert result is not None
        assert result.headers["Authorization"] == "Bearer new-token"
        assert result.headers["X-Custom-Header"] == "keep-me"

    @pytest.mark.asyncio
    async def test_called_for_all_retry_attempts(self) -> None:
        """token_refresher is invoked on every retry, not just the first."""
        tokens = ["Bearer token-1", "Bearer token-2"]
        call_count = 0

        async def rotating_refresher() -> dict[str, str]:
            nonlocal call_count
            token = tokens[call_count % len(tokens)]
            call_count += 1
            return {"Authorization": token}

        transport = _make_transport(token_refresher=rotating_refresher)
        req = httpx.Request("GET", "https://api.github.com/repos")

        result_1 = await transport.before_retry_async(req, None, 5.0, 1)
        result_2 = await transport.before_retry_async(req, None, 5.0, 2)

        assert result_1 is not None
        assert result_2 is not None
        assert result_1.headers["Authorization"] == "Bearer token-1"
        assert result_2.headers["Authorization"] == "Bearer token-2"
