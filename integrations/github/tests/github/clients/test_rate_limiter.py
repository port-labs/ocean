from http import HTTPStatus
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, cast
from _pytest.fixtures import SubRequest
import pytest
import asyncio
import gzip
import time
from unittest.mock import MagicMock, Mock, patch
import httpx

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.retry_transport import GitHubRetryTransport
from github.clients.http.base_client import AbstractGithubClient
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig, RateLimitInfo
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from github.helpers.utils import IgnoredError
from port_ocean.helpers.retry import RetryConfig


@pytest.fixture(params=[("rest", 5), ("graphql", 5), ("search", 5)])
def client_config(request: SubRequest) -> GitHubRateLimiterConfig:
    api_type, max_concurrent = request.param
    return GitHubRateLimiterConfig(api_type=api_type, max_concurrent=max_concurrent)


@pytest.fixture
def github_host() -> str:
    return "https://api.github.com"


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Mock, None, None]:
    with patch("asyncio.sleep") as m:
        yield m


@pytest.fixture(autouse=True)
def clear_rate_limiter_registry() -> Generator[None, None, None]:
    GitHubRateLimiterRegistry._instances.clear()
    yield
    GitHubRateLimiterRegistry._instances.clear()


class _DummyHeaders:
    def as_dict(self) -> dict[str, str]:
        return {}


class _DummyAuthenticator:
    def __init__(self, response: httpx.Response):
        self._response = response
        self.client = self

    async def get_headers(self, **kwargs: Any) -> _DummyHeaders:
        return _DummyHeaders()

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        return self._response


class _DummyBaseClient(AbstractGithubClient):
    def __init__(
        self,
        github_host: str,
        authenticator: _DummyAuthenticator,
        config: GitHubRateLimiterConfig,
    ):
        self._config = config
        super().__init__(
            github_host=github_host,
            authenticator=cast(AbstractGitHubAuthenticator, authenticator),
        )

    @property
    def base_url(self) -> str:
        return "https://api.github.com"

    @property
    def rate_limiter_config(self) -> GitHubRateLimiterConfig:
        return self._config

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[List[Any]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if False:
            yield []


# Helpers and constants for rate-limit issue TDD tests (see GITHUB_RATE_LIMIT_ISSUES.md)
RATE_LIMIT_HEADERS = {
    "x-ratelimit-limit": "5000",
    "x-ratelimit-remaining": "0",
    "x-ratelimit-reset": str(int(time.time()) + 3600),
}
SECONDARY_RATE_LIMIT_HEADERS = {"Retry-After": "60"}
GITHUB_HOST = "https://api.github.com"
REST_CONFIG = GitHubRateLimiterConfig(api_type="rest", max_concurrent=10)


def _make_response(
    status_code: int,
    headers: dict[str, str],
    url: str = "https://api.github.com/repos",
) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, request=request, headers=headers, content=b"{}")


class _SequenceAuthenticator:
    """Authenticator whose .client.request() returns responses from a pre-set list."""

    def __init__(
        self,
        responses: list[httpx.Response],
        delay_before_return: Optional[asyncio.Event] = None,
    ) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self._delay_before_return = delay_before_return
        self.client = self

    async def get_headers(self, **kwargs: Any) -> _DummyHeaders:
        return _DummyHeaders()

    async def request(self, **kwargs: Any) -> httpx.Response:
        idx = min(self._call_count, len(self._responses) - 1)
        resp = self._responses[idx]
        self._call_count += 1
        if self._delay_before_return is not None:
            await self._delay_before_return.wait()
        return resp

    @property
    def call_count(self) -> int:
        return self._call_count


class _DummyClient(AbstractGithubClient):
    """Concrete client for rate-limit issue tests (base_url = github_host)."""

    def __init__(
        self,
        github_host: str,
        authenticator: Any,
        config: GitHubRateLimiterConfig,
    ) -> None:
        self._config = config
        super().__init__(
            github_host=github_host,
            authenticator=cast(AbstractGitHubAuthenticator, authenticator),
        )

    @property
    def base_url(self) -> str:
        return self.github_host

    @property
    def rate_limiter_config(self) -> GitHubRateLimiterConfig:
        return self._config

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if False:
            yield []


class MockGitHubClient:
    """Mock GitHub client using the registry-provided limiter."""

    def __init__(self, host: str, config: GitHubRateLimiterConfig):
        self.github_host = host
        self.rate_limiter = GitHubRateLimiterRegistry.get_limiter(host, config)
        self.request_count = 0

    def _success_headers(self, remaining: int | None = None) -> dict[str, str]:
        """Make headers that look like GitHub's X-RateLimit set."""
        self.request_count += 1
        limit = 1000
        rem = remaining if remaining is not None else (limit - self.request_count)
        return {
            "x-ratelimit-limit": str(limit),
            "x-ratelimit-remaining": str(rem),
            "x-ratelimit-reset": str(int(time.time()) + 3600),
        }

    async def make_request(
        self,
        resource: str,
        *,
        simulate_rate_limit_error: bool = False,
        remaining_override: int | None = None,
    ) -> httpx.Response:
        async with self.rate_limiter:
            # Simulate a raw HTTP error (no headers parsed)
            if simulate_rate_limit_error:
                mock_response = Mock()
                mock_response.status_code = 429
                mock_response.headers = {}
                raise httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=mock_response
                )

            # Successful response path: update limiter from headers
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = self._success_headers(remaining=remaining_override)
            self.rate_limiter.update_rate_limits(
                httpx.Headers(mock_response.headers), resource
            )
            return mock_response


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_successful_requests_update_rate_limits(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        client = MockGitHubClient(github_host, client_config)

        resp = await client.make_request("/user")
        assert resp.status_code == 200

        info = client.rate_limiter.rate_limit_info

        assert info is not None
        assert info.limit == 1000
        assert info.remaining == 999
        assert info.utilization_percentage == 0.1

        # No sleeping purely for success
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pause_on_raw_rate_limit_error_without_headers(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """With the refactor, a bare 429 (no parsed headers) does not cause the limiter to sleep."""
        client = MockGitHubClient(github_host, client_config)

        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client.make_request("/user", simulate_rate_limit_error=True)
        assert exc.value.response.status_code == 429

        # No headers were parsed; limiter has no info and did not sleep.
        assert client.rate_limiter.rate_limit_info is None
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_enters_pause_when_remaining_le_1(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """
        If cached headers say remaining <= 1 and reset is in the future,
        the next enter should sleep.
        """
        client = MockGitHubClient(github_host, client_config)

        # Seed limiter with remaining == 1 and a short reset in the future
        reset_in = 10
        info = RateLimitInfo(
            limit=1000, remaining=1, reset_time=int(time.time()) + reset_in
        )
        client.rate_limiter.rate_limit_info = info  # trusted internal seed for the test

        # This call should sleep on __aenter__
        mock_sleep.reset_mock()
        resp = await client.make_request(
            "/user", remaining_override=999
        )  # normal success after the sleep
        assert resp.status_code == 200

        # Sleep called with at least the reset interval (may be exact or close, depending on timing)
        assert mock_sleep.call_count >= 1
        assert any(
            args[0] >= reset_in - 1 for args, _ in mock_sleep.call_args_list
        )  # allow a tiny timing skew

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_semaphore(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        client = MockGitHubClient(github_host, client_config)

        concurrent = 0
        max_seen = 0

        async def slow_request(i: int) -> httpx.Response:
            nonlocal concurrent, max_seen
            concurrent += 1
            max_seen = max(max_seen, concurrent)
            # Simulate app-level work while holding the context
            async with client.rate_limiter:
                await asyncio.sleep(0.01)
                headers = client._success_headers()
                mock_resp = Mock(status_code=200, headers=headers)
                client.rate_limiter.update_rate_limits(
                    httpx.Headers(headers), f"/r/{i}"
                )
            concurrent -= 1
            return mock_resp

        tasks = [
            asyncio.create_task(slow_request(i))
            for i in range(client_config.max_concurrent * 2)
        ]
        responses = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in responses)
        assert max_seen <= client_config.max_concurrent

    @pytest.mark.asyncio
    async def test_registry_returns_same_limiter_for_same_host_and_type(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        c1 = MockGitHubClient(github_host, client_config)
        c2 = MockGitHubClient(github_host, client_config)
        assert c1.rate_limiter is c2.rate_limiter

        await c1.make_request("/user")
        info = c2.rate_limiter.rate_limit_info

        assert info is not None
        assert info.remaining == 999

    @pytest.mark.asyncio
    async def test_success_paths_do_not_sleep(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        client = MockGitHubClient(github_host, client_config)
        resp = await client.make_request("/user")
        assert resp.status_code == 200
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_under_lock_blocks_others(
        self, github_host: str, mock_sleep: Mock
    ) -> None:
        """
        Because sleep happens while holding _block_lock, a task that triggers the pause blocks others.
        """
        config = GitHubRateLimiterConfig(api_type="rest", max_concurrent=5)
        limiter = GitHubRateLimiterRegistry.get_limiter(github_host, config)

        order: list[str] = []

        async def task_a() -> None:
            order.append("A-enter")
            # Seed limiter so that __aenter__ will sleep
            limiter.rate_limit_info = RateLimitInfo(
                remaining=0, limit=1000, reset_time=int(time.time()) + 5
            )
            async with limiter:
                order.append("A-acquired")
                # any small work
                await asyncio.sleep(0.01)
            order.append("A-exit")

        async def task_b() -> None:
            # Slightly delayed start to ensure it queues behind A
            await asyncio.sleep(0.001)
            order.append("B-enter")
            async with limiter:
                order.append("B-acquired")
                await asyncio.sleep(0.01)
            order.append("B-exit")

        t1 = asyncio.create_task(task_a())
        t2 = asyncio.create_task(task_b())
        await asyncio.gather(t1, t2)

        # Assert ordering: A acquires first and exits before B acquires (blocked by lock-held sleep)
        assert order.index("A-acquired") < order.index("B-acquired")
        assert order.index("A-exit") < order.index("B-acquired")

        # Sleep used to enforce the pause
        assert mock_sleep.call_count >= 1
        assert any(args[0] >= 5 for args, _ in mock_sleep.call_args_list)


class TestBaseClientRateLimit403Mapping:
    @pytest.mark.asyncio
    async def test_rate_limit_403_is_not_ignored(
        self, github_host: str, client_config: GitHubRateLimiterConfig, mock_sleep: Mock
    ) -> None:
        # Ensure the limiter doesn't sleep due to prior cached headers
        mock_sleep.reset_mock()

        resource = "https://api.github.com/user"
        req = httpx.Request("GET", resource)
        gzipped_body = gzip.compress(b"{}")
        resp = httpx.Response(
            403,
            request=req,
            headers={
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": str(int(time.time()) + 3600),
                "x-ratelimit-limit": "5000",
            },
            content=gzipped_body,
        )

        client = _DummyBaseClient(github_host, _DummyAuthenticator(resp), client_config)
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client.make_request(resource)
        # With the current base client behavior, rate-limit 403s are not ignored and are raised as-is.
        assert exc.value.response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_rate_limit_403_raises_when_not_ignored(
        self, github_host: str, client_config: GitHubRateLimiterConfig
    ) -> None:
        resource = "https://api.github.com/user"
        req = httpx.Request("GET", resource)
        resp = httpx.Response(403, request=req, headers={}, content=b"{}")

        client = _DummyBaseClient(github_host, _DummyAuthenticator(resp), client_config)

        with pytest.raises(httpx.HTTPStatusError):
            await client.make_request(resource, ignore_default_errors=False)


# ---------------------------------------------------------------------------
# TDD tests for the three rate-limit issues (GITHUB_RATE_LIMIT_ISSUES.md).
# They assert desired behavior and FAIL until the code is fixed; when an issue
# is fixed, the corresponding test passes and the name documents what was fixed.
# ---------------------------------------------------------------------------


class TestIssue1_RateLimiterUpdatedTooLate:
    """
    Issue 1: Rate limiter is only updated in the finally block, so concurrent
    requests see stale info. When fixed: the limiter is updated as soon as we
    receive a rate-limit response.
    """

    @pytest.mark.asyncio
    async def test_concurrent_requests_see_exhausted_quota_when_other_has_403(
        self,
    ) -> None:
        """When fixed: request B sees remaining <= 1 while A is stuck in transport with 403."""
        limiter = GitHubRateLimiterRegistry.get_limiter(GITHUB_HOST, REST_CONFIG)
        limiter.rate_limit_info = RateLimitInfo(
            remaining=100, limit=5000, reset_time=int(time.time()) + 3600
        )

        transport_gate = asyncio.Event()
        rate_limit_403 = _make_response(403, RATE_LIMIT_HEADERS)
        request_a_inside_transport = asyncio.Event()
        request_b_result: dict[str, Any] = {}

        async def request_a() -> None:
            auth = _SequenceAuthenticator(
                [rate_limit_403], delay_before_return=transport_gate
            )
            client = _DummyClient(GITHUB_HOST, auth, REST_CONFIG)
            request_a_inside_transport.set()
            try:
                await client.make_request("https://api.github.com/repos")
            except httpx.HTTPStatusError:
                pass

        async def request_b() -> None:
            await request_a_inside_transport.wait()
            await asyncio.sleep(0)
            request_b_result["remaining_before"] = (
                limiter.rate_limit_info.remaining if limiter.rate_limit_info else None
            )
            transport_gate.set()

        await asyncio.gather(
            asyncio.create_task(request_a()),
            asyncio.create_task(request_b()),
        )

        assert request_b_result["remaining_before"] is not None
        assert request_b_result["remaining_before"] <= 1, (
            "Rate limiter should be updated as soon as a 403 rate-limit response is "
            "received, so other concurrent requests see remaining <= 1."
        )

    @pytest.mark.asyncio
    async def test_limiter_updated_eagerly_while_transport_retries(self) -> None:
        """When fixed: limiter shows remaining=0 while request is still in transport."""
        transport_gate = asyncio.Event()
        rate_limit_403 = _make_response(403, RATE_LIMIT_HEADERS)
        auth = _SequenceAuthenticator(
            [rate_limit_403], delay_before_return=transport_gate
        )
        client = _DummyClient(GITHUB_HOST, auth, REST_CONFIG)
        client.rate_limiter.rate_limit_info = RateLimitInfo(
            remaining=500, limit=5000, reset_time=int(time.time()) + 3600
        )

        remaining_snapshots: list[int] = []

        async def run_request() -> None:
            try:
                await client.make_request("https://api.github.com/repos")
            except httpx.HTTPStatusError:
                pass

        async def monitor_limiter() -> None:
            await asyncio.sleep(0)
            info = client.rate_limiter.rate_limit_info
            remaining_snapshots.append(info.remaining if info else -1)
            transport_gate.set()

        await asyncio.gather(
            asyncio.create_task(run_request()),
            asyncio.create_task(monitor_limiter()),
        )

        assert remaining_snapshots == [0], (
            "Rate limiter should be updated from rate-limit response headers "
            "as soon as the response is received, not only in the finally block."
        )


class TestIssue2_PostNotRetried:
    """
    Issue 2: POST is not in retryable_methods, so GraphQL requests are never retried.
    When fixed: POST is retried like GET.
    """

    @pytest.mark.asyncio
    async def test_github_retry_transport_retries_post_requests(self) -> None:
        """When fixed: a POST that gets 429 is retried and eventually succeeds."""
        call_count = 0

        async def mock_transport_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429,
                    request=request,
                    headers={"Retry-After": "1"},
                    content=b"{}",
                )
            return httpx.Response(200, request=request, content=b"{}")

        inner_transport = MagicMock(spec=httpx.AsyncBaseTransport)
        inner_transport.handle_async_request = mock_transport_handler

        retry_config = RetryConfig(
            retry_after_headers=["Retry-After", "X-RateLimit-Reset"],
            additional_retry_status_codes=[HTTPStatus.INTERNAL_SERVER_ERROR],
            max_backoff_wait=1800,
        )
        transport = GitHubRetryTransport(
            wrapped_transport=inner_transport,
            retry_config=retry_config,
        )

        request = httpx.Request("POST", "https://api.github.com/graphql")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200, (
            "POST requests should be retried on 429/403 rate-limit and succeed."
        )
        assert call_count >= 2, (
            "Transport should retry POST (at least 2 calls: first 429, then success)."
        )


class TestIssue3_SecondaryRateLimitSwallowed:
    """
    Issue 3: 403 with only Retry-After (secondary rate limit) is treated as
    "permission denied" and returns empty data. When fixed: secondary rate-limit
    403 is either retried or raised, not silently ignored.
    """

    @pytest.mark.asyncio
    async def test_secondary_rate_limit_403_raises_instead_of_empty_response(
        self,
    ) -> None:
        """When fixed: 403 with Retry-After (secondary rate limit) is not silently ignored."""
        secondary_403 = _make_response(403, SECONDARY_RATE_LIMIT_HEADERS)
        auth = _SequenceAuthenticator([secondary_403])
        client = _DummyClient(GITHUB_HOST, auth, REST_CONFIG)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.make_request("https://api.github.com/repos")

        assert exc_info.value.response.status_code == 403
        assert exc_info.value.response.headers.get("Retry-After") == "60", (
            "Secondary rate-limit 403 (with Retry-After) should be treated as a "
            "rate limit error and raised (or retried), not returned as empty 200."
        )


class TestRateLimitIssuesControl:
    """Current correct behavior; these pass and should stay passing."""

    @pytest.mark.asyncio
    async def test_primary_rate_limit_403_is_raised(self) -> None:
        """403 with x-ratelimit-remaining: 0 is correctly raised (not ignored)."""
        primary_403 = _make_response(403, RATE_LIMIT_HEADERS)
        auth = _SequenceAuthenticator([primary_403])
        client = _DummyClient(GITHUB_HOST, auth, REST_CONFIG)

        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client.make_request("https://api.github.com/repos")
        assert exc.value.response.status_code == 403

    @pytest.mark.asyncio
    async def test_plain_permission_403_is_ignored(self) -> None:
        """403 with no rate-limit headers is correctly ignored (permission error)."""
        permission_403 = _make_response(403, {})
        auth = _SequenceAuthenticator([permission_403])
        client = _DummyClient(GITHUB_HOST, auth, REST_CONFIG)

        response = await client.make_request("https://api.github.com/repos")
        assert response.status_code == 200
        assert response.content == b"{}"

    @pytest.mark.asyncio
    async def test_get_request_is_retried(self) -> None:
        """GET that gets 429 is retried and succeeds (baseline)."""
        call_count = 0

        async def mock_transport_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429,
                    request=request,
                    headers={"Retry-After": "1"},
                    content=b"{}",
                )
            return httpx.Response(200, request=request, content=b"{}")

        inner_transport = MagicMock(spec=httpx.AsyncBaseTransport)
        inner_transport.handle_async_request = mock_transport_handler

        retry_config = RetryConfig(
            retry_after_headers=["Retry-After", "X-RateLimit-Reset"],
            additional_retry_status_codes=[HTTPStatus.INTERNAL_SERVER_ERROR],
            max_backoff_wait=1800,
        )
        transport = GitHubRetryTransport(
            wrapped_transport=inner_transport,
            retry_config=retry_config,
        )

        request = httpx.Request("GET", "https://api.github.com/repos")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200
        assert call_count == 2
