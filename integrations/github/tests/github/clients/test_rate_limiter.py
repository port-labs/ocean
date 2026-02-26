from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, cast
from _pytest.fixtures import SubRequest
import pytest
import asyncio
import gzip
import time
from unittest.mock import Mock, patch
import httpx

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.base_client import AbstractGithubClient
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig, RateLimitInfo
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry


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

    def set_rate_limit_notifier(self, notifier: Any) -> None:
        pass

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
            await self.rate_limiter.on_response(mock_response, resource)
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
        client.rate_limiter._initialized = True

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
                await client.rate_limiter.on_response(mock_resp, f"/r/{i}")
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
    async def test_notify_rate_limited_updates_state(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """
        notify_rate_limited (called synchronously from the transport) must update the
        limiter state so that the next __aenter__ sleeps.
        """
        client = MockGitHubClient(github_host, client_config)
        reset_in = 30

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {
            "x-ratelimit-limit": "1000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) + reset_in),
        }

        client.rate_limiter.notify_rate_limited(mock_response)

        # asyncio.sleep is mocked globally; use gather to let the created task actually run.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        await asyncio.gather(*pending, return_exceptions=True)

        assert client.rate_limiter._initialized is True
        assert client.rate_limiter.rate_limit_info is not None
        assert client.rate_limiter.rate_limit_info.remaining == 0

        # The next __aenter__ should sleep because remaining == 0
        mock_sleep.reset_mock()
        resp = await client.make_request("/user", remaining_override=999)
        assert resp.status_code == 200
        assert mock_sleep.call_count >= 1
        assert any(args[0] >= reset_in - 1 for args, _ in mock_sleep.call_args_list)

    @pytest.mark.asyncio
    async def test_pause_under_lock_blocks_others(
        self, github_host: str, mock_sleep: Mock
    ) -> None:
        """
        Because sleep happens while holding _lock, a task that triggers the pause blocks others.
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
            limiter._initialized = True
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


class TestRateLimiterOnResponse:
    @pytest.mark.asyncio
    async def test_on_response_does_not_reinitialize_when_already_initialized(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Once initialized from a 200, subsequent 200s do not overwrite the state."""
        client = MockGitHubClient(github_host, client_config)

        # First request: initializes to remaining=500
        await client.make_request("/user", remaining_override=500)
        assert client.rate_limiter.rate_limit_info is not None
        assert client.rate_limiter.rate_limit_info.remaining == 500

        # Second request with a different remaining: state must not be overwritten
        await client.make_request("/user", remaining_override=999)
        # Optimistic decrement from 500 → 499, but no re-init to 999
        assert client.rate_limiter.rate_limit_info.remaining == 499

    @pytest.mark.asyncio
    async def test_on_response_reinitializes_after_epoch_passes(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """After the reset epoch passes, the first new 200 reinitializes the limiter."""
        client = MockGitHubClient(github_host, client_config)

        client.rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000, remaining=5, reset_time=int(time.time()) - 1
        )
        client.rate_limiter._initialized = True

        await client.make_request("/user", remaining_override=800)
        assert client.rate_limiter.rate_limit_info is not None
        assert client.rate_limiter.rate_limit_info.remaining == 800

    @pytest.mark.asyncio
    async def test_on_response_rate_limit_403_sets_remaining_to_zero(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """A 403 with exhausted rate limit headers sets remaining=0 and marks initialized."""
        client = MockGitHubClient(github_host, client_config)

        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) + 3600),
        }
        await client.rate_limiter.on_response(mock_response, "/repos")

        assert client.rate_limiter._initialized is True
        info = client.rate_limiter.rate_limit_info
        assert info is not None
        assert info.remaining == 0

    @pytest.mark.asyncio
    async def test_handle_rate_limit_response_retry_after_only(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When only retry-after is present (no x-ratelimit headers), a fallback RateLimitInfo is created."""
        client = MockGitHubClient(github_host, client_config)
        retry_after_seconds = 30

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": str(retry_after_seconds)}
        await client.rate_limiter.on_response(mock_response, "/search")

        assert client.rate_limiter._initialized is True
        info = client.rate_limiter.rate_limit_info
        assert info is not None
        assert info.remaining == 0
        assert info.seconds_until_reset >= retry_after_seconds - 2

    @pytest.mark.asyncio
    async def test_handle_rate_limit_response_retry_after_overrides_x_ratelimit_reset(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When both x-ratelimit-reset and retry-after are present, retry-after wins."""
        client = MockGitHubClient(github_host, client_config)
        retry_after_seconds = 60

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {
            "x-ratelimit-limit": "1000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) + 3600),
            "retry-after": str(retry_after_seconds),
        }
        await client.rate_limiter.on_response(mock_response, "/repos")

        info = client.rate_limiter.rate_limit_info
        assert info is not None
        assert info.remaining == 0
        # reset_time must reflect retry-after (≈60s), not x-ratelimit-reset (≈3600s)
        assert info.seconds_until_reset <= retry_after_seconds + 2


class TestRateLimiterLogging:
    @pytest.mark.asyncio
    async def test_enforce_rate_limit_logs_bound_fields_when_sleeping(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When remaining <= 1, logger.bind is called with api_type and delay."""
        client = MockGitHubClient(github_host, client_config)
        reset_in = 15
        client.rate_limiter.rate_limit_info = RateLimitInfo(
            limit=1000, remaining=1, reset_time=int(time.time()) + reset_in
        )
        client.rate_limiter._initialized = True

        with patch("github.clients.rate_limiter.limiter.logger") as mock_logger:
            mock_bound = Mock()
            mock_logger.bind.return_value = mock_bound

            async with client.rate_limiter:
                pass

            assert mock_logger.bind.call_count == 1
            call_kwargs = mock_logger.bind.call_args.kwargs
            assert call_kwargs["api_type"] == client_config.api_type
            assert abs(call_kwargs["delay"] - reset_in) <= 2
            mock_bound.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_rate_limit_response_logs_bound_fields(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When a rate limit response is processed, logger.bind is called with api_type, resource, resets_in."""
        client = MockGitHubClient(github_host, client_config)
        reset_in = 120

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {
            "x-ratelimit-limit": "1000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time.time()) + reset_in),
        }

        with patch("github.clients.rate_limiter.limiter.logger") as mock_logger:
            mock_bound = Mock()
            mock_logger.bind.return_value = mock_bound

            await client.rate_limiter.on_response(mock_response, "/repos")

            assert mock_logger.bind.call_count == 1
            call_kwargs = mock_logger.bind.call_args.kwargs
            assert call_kwargs["api_type"] == client_config.api_type
            assert call_kwargs["resource"] == "/repos"
            assert abs(call_kwargs["resets_in"] - reset_in) <= 2
            mock_bound.warning.assert_called_once()

    def test_log_rate_limit_status_warning_when_exhausted(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When remaining == 0, _log_rate_limit_status emits a warning."""
        client = MockGitHubClient(github_host, client_config)
        info = RateLimitInfo(limit=1000, remaining=0, reset_time=int(time.time()) + 60)

        with patch("github.clients.rate_limiter.limiter.logger") as mock_logger:
            mock_bound = Mock()
            mock_logger.bind.return_value = mock_bound

            client.rate_limiter._log_rate_limit_status(info, "/user")

            mock_bound.warning.assert_called_once()
            mock_bound.debug.assert_not_called()

    def test_log_rate_limit_status_warning_when_near_exhaustion(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When remaining is at 5% of limit, _log_rate_limit_status emits a warning."""
        client = MockGitHubClient(github_host, client_config)
        info = RateLimitInfo(limit=1000, remaining=50, reset_time=int(time.time()) + 60)

        with patch("github.clients.rate_limiter.limiter.logger") as mock_logger:
            mock_bound = Mock()
            mock_logger.bind.return_value = mock_bound

            client.rate_limiter._log_rate_limit_status(info, "/user")

            mock_bound.warning.assert_called_once()
            mock_bound.debug.assert_not_called()

    def test_log_rate_limit_status_debug_when_healthy(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """When remaining is well above 10% of limit, _log_rate_limit_status emits debug."""
        client = MockGitHubClient(github_host, client_config)
        info = RateLimitInfo(
            limit=1000, remaining=500, reset_time=int(time.time()) + 60
        )

        with patch("github.clients.rate_limiter.limiter.logger") as mock_logger:
            mock_bound = Mock()
            mock_logger.bind.return_value = mock_bound

            client.rate_limiter._log_rate_limit_status(info, "/user")

            mock_bound.debug.assert_called_once()
            mock_bound.warning.assert_not_called()


class TestNotifyRateLimitedConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_notify_calls_produce_consistent_state(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Multiple concurrent notify_rate_limited calls must not corrupt the limiter state."""
        client = MockGitHubClient(github_host, client_config)
        now = int(time.time())

        def make_429(reset_in: int) -> Mock:
            resp = Mock()
            resp.status_code = 429
            resp.headers = {
                "x-ratelimit-limit": "1000",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": str(now + reset_in),
            }
            return resp

        for reset_in in [10, 20, 30]:
            client.rate_limiter.notify_rate_limited(make_429(reset_in))

        # asyncio.sleep is mocked; gather pending tasks to flush all _apply_rate_limit coroutines.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        await asyncio.gather(*pending, return_exceptions=True)

        info = client.rate_limiter.rate_limit_info
        assert info is not None
        assert info.remaining == 0
        assert client.rate_limiter._initialized is True
        assert info.reset_time in {now + 10, now + 20, now + 30}

    @pytest.mark.asyncio
    async def test_notify_rate_limited_while_enforce_holds_lock_is_deferred(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """notify_rate_limited schedules as a task and runs after the current lock holder releases."""
        client = MockGitHubClient(github_host, client_config)
        now = int(time.time())

        notify_response = Mock()
        notify_response.status_code = 429
        notify_response.headers = {
            "x-ratelimit-limit": "1000",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(now + 5),
        }

        # Fire notify while we still haven't released the lock
        async with client.rate_limiter._lock:
            client.rate_limiter.notify_rate_limited(notify_response)
            # Task is scheduled but cannot run yet — lock is held
            assert client.rate_limiter.rate_limit_info is None

        # Lock is now released; gather the pending task to let _apply_rate_limit run.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        await asyncio.gather(*pending, return_exceptions=True)

        assert client.rate_limiter._initialized is True
        assert client.rate_limiter.rate_limit_info is not None
        assert client.rate_limiter.rate_limit_info.remaining == 0


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
