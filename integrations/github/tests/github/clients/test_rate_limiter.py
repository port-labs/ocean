import pytest
import asyncio
import time
from typing import Any
from unittest.mock import Mock, patch
import httpx

from github.clients.rate_limiter import GitHubRateLimiter, RateLimitInfo
from github.helpers.exceptions import RateLimitExceededError


class MockGitHubAPI:
    """Mock GitHub API for testing rate limit scenarios."""

    def __init__(self) -> None:
        self.request_count = 0
        self.rate_limit_reset_time = int(time.time()) + 3600
        self.search_reset_time = int(time.time()) + 60

    def get_mock_response(self, endpoint: str, status_code: int = 200) -> Mock:
        """Create a mock response with appropriate headers."""
        response = Mock()
        response.status_code = status_code
        response.headers = {}

        # Add rate limit headers based on endpoint
        if "/search/" in endpoint:
            # Search rate limit: 30 requests/minute
            remaining = max(0, 30 - (self.request_count % 35))  # Exhaust after 30
            response.headers.update(
                {
                    "x-ratelimit-limit": "30",
                    "x-ratelimit-remaining": str(remaining),
                    "x-ratelimit-reset": str(self.search_reset_time),
                }
            )
        else:
            # Core rate limit: 5000 requests/hour
            remaining = max(0, 5000 - (self.request_count % 5005))  # Exhaust after 5000
            response.headers.update(
                {
                    "x-ratelimit-limit": "5000",
                    "x-ratelimit-remaining": str(remaining),
                    "x-ratelimit-reset": str(self.rate_limit_reset_time),
                }
            )

        # Simulate rate limit errors
        if remaining == 0:
            response.status_code = 403
            response.headers["Retry-After"] = "60"

        self.request_count += 1
        return response


@pytest.mark.no_mock_rate_limiter
@pytest.mark.asyncio
class TestGitHubRateLimiter:
    """Comprehensive test suite for GitHub Rate Limiter."""

    @pytest.fixture
    def rate_limiter(self) -> GitHubRateLimiter:
        """Create a rate limiter instance for testing."""
        return GitHubRateLimiter(max_retries=3, max_concurrent=5)

    @pytest.fixture
    def mock_api(self) -> MockGitHubAPI:
        """Create a mock GitHub API for testing."""
        return MockGitHubAPI()

    async def test_basic_functionality(self, rate_limiter: GitHubRateLimiter) -> None:
        """Test basic rate limiter functionality."""
        # Test initialization
        assert rate_limiter.max_retries == 3
        assert rate_limiter._semaphore._value == 5

        # Test resource type detection
        assert (
            rate_limiter._determine_resource_type("https://api.github.com/user")
            == "core"
        )
        assert (
            rate_limiter._determine_resource_type(
                "https://api.github.com/search/repositories"
            )
            == "search"
        )
        assert (
            rate_limiter._determine_resource_type("https://api.github.com/graphql")
            == "graphql"
        )
        assert (
            rate_limiter._determine_resource_type("https://api.github.com/search/code")
            == "search"
        )

    async def test_rate_limit_header_parsing(
        self, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test parsing of GitHub rate limit headers."""
        # Test valid headers
        mock_response = Mock()
        mock_response.headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "4999",
            "x-ratelimit-reset": str(int(time.time()) + 3600),
        }

        rate_limit_info = rate_limiter._parse_rate_limit_headers(mock_response)
        assert rate_limit_info is not None
        assert rate_limit_info.limit == 5000
        assert rate_limit_info.remaining == 4999
        assert rate_limit_info.reset_time > time.time()

        # Test missing headers
        mock_response.headers = {}
        rate_limit_info = rate_limiter._parse_rate_limit_headers(mock_response)
        assert rate_limit_info is None

        # Test partial headers
        mock_response.headers = {"x-ratelimit-limit": "5000"}
        rate_limit_info = rate_limiter._parse_rate_limit_headers(mock_response)
        assert rate_limit_info is None

    async def test_backoff_calculation(self, rate_limiter: GitHubRateLimiter) -> None:
        """Test backoff time calculation."""
        # Test secondary rate limit (429) with Retry-After
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}

        backoff_time = rate_limiter._get_backoff_time(mock_response)
        assert backoff_time == 120.0  # Should use Retry-After value

        # Test primary rate limit (403) with X-RateLimit-Reset
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Reset": str(int(time.time()) + 1800)  # 30 minutes from now
        }

        backoff_time = rate_limiter._get_backoff_time(mock_response)
        # Fix the type comparison issue by checking for None first
        assert backoff_time is not None
        assert 1750 <= backoff_time <= 1850  # Should be ~30 minutes

        # Test minimum backoff time
        mock_response.headers = {"Retry-After": "30"}
        backoff_time = rate_limiter._get_backoff_time(mock_response)
        assert backoff_time == 60.0  # Should be minimum 60 seconds

        # Test no backoff needed
        mock_response.status_code = 200
        mock_response.headers = {}
        backoff_time = rate_limiter._get_backoff_time(mock_response)
        assert backoff_time is None

    async def test_rate_limit_error_detection(
        self, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test rate limit error detection."""
        # Test 403 with rate limit headers
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "Retry-After": "60",
        }

        backoff_time = rate_limiter._handle_rate_limit_error(
            mock_response, "/test", "core"
        )
        assert backoff_time is not None

        # Test 429 with Retry-After
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}

        backoff_time = rate_limiter._handle_rate_limit_error(
            mock_response, "/test", "core"
        )
        assert backoff_time == 120.0

        # Test 403 without rate limit headers (permission error)
        mock_response.status_code = 403
        mock_response.headers = {}

        backoff_time = rate_limiter._handle_rate_limit_error(
            mock_response, "/test", "core"
        )
        assert backoff_time is None

        # Test non-rate limit error
        mock_response.status_code = 404
        mock_response.headers = {}

        backoff_time = rate_limiter._handle_rate_limit_error(
            mock_response, "/test", "core"
        )
        assert backoff_time is None

    @patch("asyncio.sleep")
    async def test_concurrency_control(
        self, mock_sleep: Any, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test semaphore-based concurrency control."""
        # Create a rate limiter with lower concurrency for testing
        test_rate_limiter = GitHubRateLimiter(max_concurrent=3)

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0

        async def mock_request_func(resource: str, **kwargs: Any) -> Mock:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

            # Simulate request time
            await asyncio.sleep(0.001)  # Very short delay

            concurrent_count -= 1
            return Mock(status_code=200, headers={})

        # Create many concurrent requests
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                test_rate_limiter.execute_request(
                    mock_request_func, f"https://api.github.com/test{i}"
                )
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Should never exceed max_concurrent
        assert max_concurrent <= 3
        assert concurrent_count == 0  # All should complete

    @patch("asyncio.sleep")
    async def test_retry_logic(
        self, mock_sleep: Any, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test retry logic for different error types."""
        # Create a rate limiter with specific retry settings
        test_rate_limiter = GitHubRateLimiter(max_retries=2)

        # Test successful request (no retries)
        call_count = 0

        async def success_request_func(resource: str, **kwargs: Any) -> Mock:
            nonlocal call_count
            call_count += 1
            return Mock(status_code=200, headers={})

        response = await test_rate_limiter.execute_request(
            success_request_func, "https://api.github.com/test"
        )
        assert response.status_code == 200
        assert call_count == 1

        # Test rate limit with retry
        call_count = 0

        async def rate_limit_request_func(resource: str, **kwargs: Any) -> Mock:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: rate limit
                response = Mock()
                response.status_code = 429
                response.headers = {"Retry-After": "0.1"}  # Short delay for testing
                raise httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=response
                )
            else:
                # Second call: success
                return Mock(status_code=200, headers={})

        response = await test_rate_limiter.execute_request(
            rate_limit_request_func, "https://api.github.com/test"
        )
        assert response.status_code == 200
        assert call_count == 2

        # Test max retries exceeded
        call_count = 0

        async def always_fail_request_func(resource: str, **kwargs: Any) -> Mock:
            nonlocal call_count
            call_count += 1

            response = Mock()
            response.status_code = 429
            response.headers = {"Retry-After": "0.1"}
            raise httpx.HTTPStatusError(
                "Always rate limited", request=Mock(), response=response
            )

        with pytest.raises(RateLimitExceededError):
            await test_rate_limiter.execute_request(
                always_fail_request_func, "https://api.github.com/test"
            )

        assert call_count == 3  # Initial + 2 retries

    async def test_resource_type_tracking(
        self, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test separate tracking of different resource types."""

        # Mock responses for different resource types
        async def mock_request_func(resource: str, **kwargs: Any) -> Mock:
            response = Mock()
            response.status_code = 200

            if "/search/" in resource:
                response.headers = {
                    "x-ratelimit-limit": "30",
                    "x-ratelimit-remaining": "25",
                    "x-ratelimit-reset": str(int(time.time()) + 60),
                }
            else:
                response.headers = {
                    "x-ratelimit-limit": "5000",
                    "x-ratelimit-remaining": "4995",
                    "x-ratelimit-reset": str(int(time.time()) + 3600),
                }

            return response

        # Make requests to different resource types
        await rate_limiter.execute_request(
            mock_request_func, "https://api.github.com/user"
        )
        await rate_limiter.execute_request(
            mock_request_func, "https://api.github.com/search/repositories"
        )
        await rate_limiter.execute_request(
            mock_request_func, "https://api.github.com/graphql"
        )

        # Check that different resource types are tracked separately
        status = rate_limiter.get_rate_limit_status()
        assert "core" in status
        assert "search" in status
        assert "graphql" in status

        # Verify the values
        assert status["core"]["remaining"] == 4995
        assert status["search"]["remaining"] == 25
        assert status["graphql"]["remaining"] == 4995  # Same as core

    async def test_monitoring_and_logging(
        self, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test monitoring and logging functionality."""
        # Test empty status
        status = rate_limiter.get_rate_limit_status()
        assert status == {}

        # Test status with data
        rate_limiter._rate_limits["core"] = RateLimitInfo(
            limit=5000, remaining=4999, reset_time=int(time.time()) + 3600
        )

        status = rate_limiter.get_rate_limit_status()
        assert "core" in status
        assert status["core"]["remaining"] == 4999
        assert status["core"]["limit"] == 5000

        # Test logging (should not raise exceptions)
        rate_limiter.log_rate_limit_status()

    @patch("asyncio.sleep")
    async def test_performance_under_load(
        self, mock_sleep: Any, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Test performance under high load."""
        # Create a rate limiter with higher concurrency for load testing
        test_rate_limiter = GitHubRateLimiter(max_concurrent=10, max_retries=1)

        start_time = time.time()

        async def fast_request_func(resource: str, **kwargs: Any) -> Mock:
            await asyncio.sleep(0.001)  # Simulate fast request
            return Mock(status_code=200, headers={})

        # Create many concurrent requests
        tasks = []
        for i in range(100):
            task = asyncio.create_task(
                test_rate_limiter.execute_request(
                    fast_request_func, f"https://api.github.com/test{i}"
                )
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        end_time = time.time()
        duration = end_time - start_time

        assert duration < 10  # Should complete reasonably quickly

    @patch("asyncio.sleep")
    async def test_rate_limit_exhaustion_simulation(
        self, mock_sleep: Any, rate_limiter: GitHubRateLimiter
    ) -> None:
        """Simulate rate limit exhaustion scenarios."""
        # Create a rate limiter with specific retry settings
        test_rate_limiter = GitHubRateLimiter(max_retries=2)

        # Simulate core rate limit exhaustion
        call_count = 0

        async def core_exhaustion_func(resource: str, **kwargs: Any) -> Mock:
            nonlocal call_count
            call_count += 1

            response = Mock()
            if call_count <= 2:
                # First two calls: rate limit
                response.status_code = 403
                response.headers = {
                    "X-RateLimit-Reset": str(int(time.time()) + 3600),
                    "Retry-After": "0.1",
                }
                raise httpx.HTTPStatusError(
                    "Core rate limited", request=Mock(), response=response
                )
            else:
                # Third call: success
                response.status_code = 200
                response.headers = {
                    "x-ratelimit-limit": "5000",
                    "x-ratelimit-remaining": "4999",
                    "x-ratelimit-reset": str(int(time.time()) + 3600),
                }
                return response

        response = await test_rate_limiter.execute_request(
            core_exhaustion_func, "https://api.github.com/user"
        )
        assert response.status_code == 200
        assert call_count == 3

        # Simulate search rate limit exhaustion
        call_count = 0

        async def search_exhaustion_func(resource: str, **kwargs: Any) -> Mock:
            nonlocal call_count
            call_count += 1

            response = Mock()
            if call_count <= 1:
                # First call: search rate limit
                response.status_code = 429
                response.headers = {"Retry-After": "0.1"}
                raise httpx.HTTPStatusError(
                    "Search rate limited", request=Mock(), response=response
                )
            else:
                # Second call: success
                response.status_code = 200
                response.headers = {
                    "x-ratelimit-limit": "30",
                    "x-ratelimit-remaining": "29",
                    "x-ratelimit-reset": str(int(time.time()) + 60),
                }
                return response

        response = await test_rate_limiter.execute_request(
            search_exhaustion_func, "https://api.github.com/search/repositories"
        )
        assert response.status_code == 200
        assert call_count == 2
