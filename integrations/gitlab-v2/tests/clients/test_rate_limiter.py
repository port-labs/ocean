import asyncio
import time
from typing import Generator
from unittest.mock import Mock, patch

import httpx
import pytest

from gitlab.clients.rate_limiter.limiter import GitLabRateLimiter
from gitlab.clients.rate_limiter.registry import GitLabRateLimiterRegistry
from gitlab.clients.rate_limiter.utils import (
    GitLabRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
    has_exhausted_rate_limit_headers,
)


@pytest.fixture
def config() -> GitLabRateLimiterConfig:
    """Create a rate limiter config with low concurrency for testing."""
    return GitLabRateLimiterConfig(max_concurrent=5)


@pytest.fixture
def gitlab_host() -> str:
    """Provide a test GitLab host."""
    return "https://gitlab.example.com"


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Mock, None, None]:
    """Mock asyncio.sleep to avoid actual delays in tests."""
    with patch("gitlab.clients.rate_limiter.limiter.asyncio.sleep") as m:
        yield m


@pytest.fixture(autouse=True)
def clear_rate_limiter_registry() -> Generator[None, None, None]:
    """Clear the registry before and after each test."""
    GitLabRateLimiterRegistry.clear()
    yield
    GitLabRateLimiterRegistry.clear()


class MockGitLabClient:
    """Mock GitLab client using the registry-provided limiter."""

    def __init__(self, host: str, config: GitLabRateLimiterConfig):
        self.gitlab_host = host
        self.rate_limiter = GitLabRateLimiterRegistry.get_limiter(host, config)
        self.request_count = 0

    def _success_headers(self, remaining: int | None = None) -> dict[str, str]:
        """Make headers that look like GitLab's RateLimit set."""
        self.request_count += 1
        limit = 1000
        rem = remaining if remaining is not None else (limit - self.request_count)
        return {
            "ratelimit-limit": str(limit),
            "ratelimit-remaining": str(rem),
            "ratelimit-reset": str(int(time.time()) + 3600),
        }

    async def make_request(
        self,
        resource: str,
        *,
        simulate_rate_limit_error: bool = False,
        remaining_override: int | None = None,
    ) -> httpx.Response:
        async with self.rate_limiter:
            if simulate_rate_limit_error:
                mock_response = Mock()
                mock_response.status_code = 429
                mock_response.headers = {}
                raise httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=mock_response
                )

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = self._success_headers(remaining=remaining_override)
            self.rate_limiter.update_rate_limits(
                httpx.Headers(mock_response.headers)
            )
            return mock_response


class TestRateLimitInfo:
    def test_seconds_until_reset_positive(self) -> None:
        """Test seconds_until_reset returns positive value when reset is in future."""
        info = RateLimitInfo(
            limit=1000,
            remaining=500,
            reset_time=int(time.time()) + 60,
        )
        seconds = info.seconds_until_reset
        assert 59 <= seconds <= 60

    def test_seconds_until_reset_zero_when_past(self) -> None:
        """Test seconds_until_reset returns 0 when reset time is in the past."""
        info = RateLimitInfo(
            limit=1000,
            remaining=0,
            reset_time=int(time.time()) - 60,
        )
        assert info.seconds_until_reset == 0

    def test_utilization_percentage_half_used(self) -> None:
        """Test utilization_percentage when half the limit is used."""
        info = RateLimitInfo(
            limit=1000,
            remaining=500,
            reset_time=int(time.time()) + 60,
        )
        assert info.utilization_percentage == 50.0

    def test_utilization_percentage_fully_used(self) -> None:
        """Test utilization_percentage when limit is fully used."""
        info = RateLimitInfo(
            limit=1000,
            remaining=0,
            reset_time=int(time.time()) + 60,
        )
        assert info.utilization_percentage == 100.0

    def test_utilization_percentage_zero_limit(self) -> None:
        """Test utilization_percentage handles zero limit gracefully."""
        info = RateLimitInfo(
            limit=0,
            remaining=0,
            reset_time=int(time.time()) + 60,
        )
        assert info.utilization_percentage == 0.0


class TestGitLabRateLimiterConfig:
    def test_default_max_concurrent(self) -> None:
        """Test default max_concurrent value."""
        config = GitLabRateLimiterConfig()
        assert config.max_concurrent == 10

    def test_custom_max_concurrent(self) -> None:
        """Test custom max_concurrent value."""
        config = GitLabRateLimiterConfig(max_concurrent=50)
        assert config.max_concurrent == 50


class TestRateLimiterRequiredHeaders:
    def test_parse_headers_from_dict(self) -> None:
        """Test parsing rate limit headers from dict."""
        headers = {
            "ratelimit-limit": "60",
            "ratelimit-remaining": "45",
            "ratelimit-reset": "1609459200",
        }
        parsed = RateLimiterRequiredHeaders(**headers)
        assert parsed.ratelimit_limit == "60"
        assert parsed.ratelimit_remaining == "45"
        assert parsed.ratelimit_reset == "1609459200"

    def test_parse_headers_missing_values(self) -> None:
        """Test parsing headers with missing values returns None."""
        headers = {"other-header": "value"}
        parsed = RateLimiterRequiredHeaders(**headers)
        assert parsed.ratelimit_limit is None
        assert parsed.ratelimit_remaining is None
        assert parsed.ratelimit_reset is None


class TestHasExhaustedRateLimitHeaders:
    def test_exhausted_with_string_zero(self) -> None:
        """Test detection when remaining is string '0'."""
        headers = {
            "ratelimit-remaining": "0",
            "ratelimit-reset": "1609459200",
        }
        assert has_exhausted_rate_limit_headers(headers) is True

    def test_exhausted_with_int_zero(self) -> None:
        """Test detection when remaining is integer 0."""
        headers = {
            "ratelimit-remaining": 0,
            "ratelimit-reset": "1609459200",
        }
        assert has_exhausted_rate_limit_headers(headers) is True

    def test_not_exhausted_with_remaining(self) -> None:
        """Test returns False when remaining > 0."""
        headers = {
            "ratelimit-remaining": "10",
            "ratelimit-reset": "1609459200",
        }
        assert has_exhausted_rate_limit_headers(headers) is False

    def test_not_exhausted_without_reset(self) -> None:
        """Test returns False when reset header is missing."""
        headers = {
            "ratelimit-remaining": "0",
        }
        assert has_exhausted_rate_limit_headers(headers) is False

    def test_not_exhausted_empty_headers(self) -> None:
        """Test returns False with empty headers."""
        headers = {}
        assert has_exhausted_rate_limit_headers(headers) is False


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_successful_requests_update_rate_limits(
        self, config: GitLabRateLimiterConfig, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """Test that successful requests update rate limit tracking."""
        client = MockGitLabClient(gitlab_host, config)

        resp = await client.make_request("/projects")
        assert resp.status_code == 200

        info = client.rate_limiter.rate_limit_info

        assert info is not None
        assert info.limit == 1000
        assert info.remaining == 999
        assert info.utilization_percentage == 0.1

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_pause_on_raw_rate_limit_error_without_headers(
        self, config: GitLabRateLimiterConfig, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """A bare 429 (no parsed headers) does not cause the limiter to sleep."""
        client = MockGitLabClient(gitlab_host, config)

        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client.make_request("/projects", simulate_rate_limit_error=True)
        assert exc.value.response.status_code == 429

        assert client.rate_limiter.rate_limit_info is None
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_enters_pause_when_remaining_le_max_concurrent(
        self, config: GitLabRateLimiterConfig, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """If cached headers say remaining <= max_concurrent, the next enter should sleep."""
        client = MockGitLabClient(gitlab_host, config)

        reset_in = 10
        info = RateLimitInfo(
            limit=1000, remaining=5, reset_time=int(time.time()) + reset_in
        )
        client.rate_limiter.rate_limit_info = info

        mock_sleep.reset_mock()
        resp = await client.make_request("/projects", remaining_override=999)
        assert resp.status_code == 200

        assert mock_sleep.call_count >= 1
        assert any(
            args[0] >= reset_in - 1 for args, _ in mock_sleep.call_args_list
        )

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_semaphore(
        self, config: GitLabRateLimiterConfig, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """Test that concurrent requests are limited by semaphore."""
        client = MockGitLabClient(gitlab_host, config)

        concurrent = 0
        max_seen = 0

        async def slow_request(i: int) -> httpx.Response:
            nonlocal concurrent, max_seen
            concurrent += 1
            max_seen = max(max_seen, concurrent)
            async with client.rate_limiter:
                await asyncio.sleep(0.01)
                headers = client._success_headers()
                mock_resp = Mock(status_code=200, headers=headers)
                client.rate_limiter.update_rate_limits(
                    httpx.Headers(headers)
                )
            concurrent -= 1
            return mock_resp

        tasks = [
            asyncio.create_task(slow_request(i))
            for i in range(config.max_concurrent * 2)
        ]
        responses = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in responses)
        assert max_seen <= config.max_concurrent

    @pytest.mark.asyncio
    async def test_registry_returns_same_limiter_for_same_host(
        self, config: GitLabRateLimiterConfig, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """Test that registry returns same instance for same host."""
        c1 = MockGitLabClient(gitlab_host, config)
        c2 = MockGitLabClient(gitlab_host, config)
        assert c1.rate_limiter is c2.rate_limiter

        await c1.make_request("/projects")
        info = c2.rate_limiter.rate_limit_info

        assert info is not None
        assert info.remaining == 999

    @pytest.mark.asyncio
    async def test_success_paths_do_not_sleep(
        self, config: GitLabRateLimiterConfig, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """Test that successful requests don't cause any sleeping."""
        client = MockGitLabClient(gitlab_host, config)
        resp = await client.make_request("/projects")
        assert resp.status_code == 200
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_under_lock_blocks_others(
        self, gitlab_host: str, mock_sleep: Mock
    ) -> None:
        """Because sleep happens while holding _block_lock, a task that triggers the pause blocks others."""
        config = GitLabRateLimiterConfig(max_concurrent=5)
        limiter = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        order: list[str] = []

        async def task_a() -> None:
            order.append("A-enter")
            limiter.rate_limit_info = RateLimitInfo(
                remaining=0, limit=1000, reset_time=int(time.time()) + 5
            )
            async with limiter:
                order.append("A-acquired")
                await asyncio.sleep(0.01)
            order.append("A-exit")

        async def task_b() -> None:
            await asyncio.sleep(0.001)
            order.append("B-enter")
            async with limiter:
                order.append("B-acquired")
                await asyncio.sleep(0.01)
            order.append("B-exit")

        t1 = asyncio.create_task(task_a())
        t2 = asyncio.create_task(task_b())
        await asyncio.gather(t1, t2)

        assert order.index("A-acquired") < order.index("B-acquired")
        assert order.index("A-exit") < order.index("B-acquired")

        assert mock_sleep.call_count >= 1
        assert any(args[0] >= 5 for args, _ in mock_sleep.call_args_list)


class TestRateLimiterIsRateLimitResponse:
    @pytest.fixture
    def rate_limiter(self) -> GitLabRateLimiter:
        """Create a rate limiter for response checking tests."""
        return GitLabRateLimiter(GitLabRateLimiterConfig(max_concurrent=10))

    def test_429_is_rate_limit(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test 429 response is detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 429
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is True

    def test_403_with_exhausted_headers_is_rate_limit(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test 403 with exhausted rate limit headers is detected."""
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {
            "ratelimit-remaining": "0",
            "ratelimit-reset": "1609459200",
        }

        assert rate_limiter.is_rate_limit_response(response) is True

    def test_403_without_exhausted_headers_is_not_rate_limit(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test 403 without rate limit headers is not detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is False

    def test_200_is_not_rate_limit(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test 200 response is not detected as rate limit."""
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.headers = {}

        assert rate_limiter.is_rate_limit_response(response) is False


class TestRateLimiterUpdateRateLimits:
    @pytest.fixture
    def rate_limiter(self) -> GitLabRateLimiter:
        """Create a rate limiter for update tests."""
        return GitLabRateLimiter(GitLabRateLimiterConfig(max_concurrent=10))

    def test_update_with_valid_headers(self, rate_limiter: GitLabRateLimiter) -> None:
        """Test updating rate limits from valid response headers."""
        headers = httpx.Headers(
            {
                "ratelimit-limit": "60",
                "ratelimit-remaining": "45",
                "ratelimit-reset": str(int(time.time()) + 60),
            }
        )

        result = rate_limiter.update_rate_limits(headers)

        assert result is not None
        assert result.limit == 60
        assert result.remaining == 45
        assert rate_limiter.rate_limit_info is result

    def test_update_with_missing_headers(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test updating with missing headers returns None."""
        headers = httpx.Headers({"other-header": "value"})

        result = rate_limiter.update_rate_limits(headers)

        assert result is None
        assert rate_limiter.rate_limit_info is None

    def test_update_overwrites_previous_info(
        self, rate_limiter: GitLabRateLimiter
    ) -> None:
        """Test that new headers overwrite previous rate limit info."""
        rate_limiter.rate_limit_info = RateLimitInfo(
            limit=100,
            remaining=50,
            reset_time=int(time.time()) + 30,
        )

        headers = httpx.Headers(
            {
                "ratelimit-limit": "60",
                "ratelimit-remaining": "10",
                "ratelimit-reset": str(int(time.time()) + 120),
            }
        )
        result = rate_limiter.update_rate_limits(headers)

        assert result is not None
        assert result.limit == 60
        assert result.remaining == 10


class TestRateLimiterRegistry:
    def test_get_limiter_creates_new_instance(
        self, gitlab_host: str, config: GitLabRateLimiterConfig
    ) -> None:
        """Test that get_limiter creates a new limiter for unknown host."""
        limiter = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        assert limiter is not None
        assert isinstance(limiter, GitLabRateLimiter)

    def test_get_limiter_returns_same_instance_for_same_host(
        self, gitlab_host: str, config: GitLabRateLimiterConfig
    ) -> None:
        """Test that get_limiter returns same instance for same host."""
        limiter1 = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)
        limiter2 = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        assert limiter1 is limiter2

    def test_get_limiter_returns_different_instances_for_different_hosts(
        self, config: GitLabRateLimiterConfig
    ) -> None:
        """Test that different hosts get different limiter instances."""
        host1 = "https://gitlab.example.com"
        host2 = "https://gitlab.other.com"

        limiter1 = GitLabRateLimiterRegistry.get_limiter(host1, config)
        limiter2 = GitLabRateLimiterRegistry.get_limiter(host2, config)

        assert limiter1 is not limiter2

    def test_clear_removes_all_instances(
        self, gitlab_host: str, config: GitLabRateLimiterConfig
    ) -> None:
        """Test that clear() removes all registered limiters."""
        GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)
        GitLabRateLimiterRegistry.get_limiter("https://other.gitlab.com", config)

        GitLabRateLimiterRegistry.clear()

        assert len(GitLabRateLimiterRegistry._instances) == 0

    def test_limiter_uses_provided_config(self, gitlab_host: str) -> None:
        """Test that limiter is created with provided config."""
        config = GitLabRateLimiterConfig(max_concurrent=25)

        limiter = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        assert limiter._max_concurrent == 25
