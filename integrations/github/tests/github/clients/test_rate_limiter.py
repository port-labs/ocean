from typing import Generator
import pytest
import asyncio
import time
from unittest.mock import Mock, patch
import httpx

from github.clients.rate_limiter.utils import GitHubRateLimiterConfig
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry
from _pytest.fixtures import SubRequest


@pytest.fixture(params=[("rest", 3, 5), ("graphql", 2, 3), ("search", 1, 2)])
def client_config(request: SubRequest) -> GitHubRateLimiterConfig:
    """Parameterized fixture for different client configurations."""
    api_type, max_retries, max_concurrent = request.param
    return GitHubRateLimiterConfig(
        api_type=api_type, max_retries=max_retries, max_concurrent=max_concurrent
    )


@pytest.fixture
def github_host() -> str:
    """GitHub host fixture."""
    return "https://api.github.com"


@pytest.fixture(autouse=True)
def mock_sleep() -> Generator[Mock, None, None]:
    """Mock asyncio.sleep to speed up tests."""
    with patch("asyncio.sleep") as mock_sleep:
        yield mock_sleep


@pytest.fixture(autouse=True)
def clear_rate_limiter_registry() -> Generator[None, None, None]:
    """Clear the rate limiter registry before each test to ensure clean state."""
    GitHubRateLimiterRegistry._instances.clear()
    yield
    GitHubRateLimiterRegistry._instances.clear()


class MockGitHubClient:
    """Mock GitHub client that uses rate limiter like the real clients."""

    def __init__(self, host: str, config: GitHubRateLimiterConfig):
        self.github_host = host
        self.rate_limiter = GitHubRateLimiterRegistry.get_limiter(host, config)
        self.request_count = 0

    async def make_request(
        self, resource: str, simulate_rate_limit: bool = False
    ) -> httpx.Response:
        """Simulate making a request with rate limiting."""
        async with self.rate_limiter:
            self.request_count += 1

            # Simulate rate limit on first request if requested
            if simulate_rate_limit and self.request_count == 1:
                mock_response = Mock()
                mock_response.status_code = 429
                mock_response.headers = {"Retry-After": "0.1"}
                raise httpx.HTTPStatusError(
                    "Rate limited", request=Mock(), response=mock_response
                )

            # Simulate successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_headers = {
                "x-ratelimit-limit": "1000",
                "x-ratelimit-remaining": str(1000 - self.request_count),
                "x-ratelimit-reset": str(int(time.time()) + 3600),
            }
            mock_response.headers = mock_headers

            # Update rate limit info
            self.rate_limiter.update_rate_limits(httpx.Headers(mock_headers), resource)
            return mock_response


class TestRateLimiterIntegration:
    """Integration tests showing how rate limiter works with HTTP clients."""

    @pytest.mark.asyncio
    async def test_successful_requests_update_rate_limits(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that successful requests update rate limit information."""
        client = MockGitHubClient(github_host, client_config)

        # Make a request
        response = await client.make_request("/user")

        assert response.status_code == 200

        # Check rate limit status
        status = client.rate_limiter.get_rate_limit_status()
        assert client_config.api_type in status
        assert status[client_config.api_type]["limit"] == 1000
        assert status[client_config.api_type]["remaining"] == 999
        assert status[client_config.api_type]["utilization_percentage"] == 0.1

    @pytest.mark.asyncio
    async def test_rate_limit_error_pauses_requests(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that rate limit errors pause subsequent requests."""
        client = MockGitHubClient(github_host, client_config)

        # First request hits rate limit - should be handled by context manager
        response = await client.make_request("/user", simulate_rate_limit=True)

        # Should return None because context manager handled the rate limit but didn't retry
        assert response is None

        # Rate limiter should be paused
        assert client.rate_limiter.is_paused()

        # Verify that sleep was called with the backoff time (may be called multiple times)
        assert mock_sleep.call_count >= 1
        # Check that one of the calls was with the expected backoff time
        # 5.1 comes from: 0.1 (default Retry-After in mock) + 5.0 (buffer added by rate limiter)
        assert any(call.args[0] == 5.1 for call in mock_sleep.call_args_list)

        # Reset mock for next call
        mock_sleep.reset_mock()

        # Second request should succeed (but will sleep due to pause)
        response = await client.make_request("/user")
        assert response.status_code == 200

        # Should have called sleep again because pause is still active
        assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_rate_limits(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that concurrent requests respect rate limits."""
        client = MockGitHubClient(github_host, client_config)

        # Create concurrent requests
        tasks = []
        for i in range(10):
            task = asyncio.create_task(client.make_request(f"/user/{i}"))
            tasks.append(task)

        # All should complete successfully
        responses = await asyncio.gather(*tasks)
        assert len(responses) == 10
        assert all(response.status_code == 200 for response in responses)

        # Check final rate limit status
        status = client.rate_limiter.get_rate_limit_status()
        assert status[client_config.api_type]["remaining"] == 990  # 1000 - 10 requests

    @pytest.mark.asyncio
    async def test_registry_returns_same_limiter_for_same_host_and_type(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that registry returns the same limiter instance for same host and API type."""
        client1 = MockGitHubClient(github_host, client_config)
        client2 = MockGitHubClient(github_host, client_config)

        # Should get the same rate limiter instance
        assert client1.rate_limiter is client2.rate_limiter

        # Make a request with first client
        await client1.make_request("/user")

        # Check that second client sees the updated rate limit info
        status = client2.rate_limiter.get_rate_limit_status()
        assert status[client_config.api_type]["remaining"] == 999

    @pytest.mark.asyncio
    async def test_rate_limit_status_monitoring(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test monitoring rate limit status during requests."""
        client = MockGitHubClient(github_host, client_config)

        # Initial status should be empty
        status = client.rate_limiter.get_rate_limit_status()
        assert status == {}

        # Make several requests and monitor status
        for i in range(3):
            response = await client.make_request(f"/user/{i}")
            assert response.status_code == 200

            status = client.rate_limiter.get_rate_limit_status()
            assert status[client_config.api_type]["remaining"] == 1000 - (i + 1)
            assert (
                status[client_config.api_type]["utilization_percentage"]
                == ((i + 1) / 1000) * 100
            )

    @pytest.mark.asyncio
    async def test_context_manager_handles_exceptions(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that context manager properly handles exceptions."""
        client = MockGitHubClient(github_host, client_config)

        # Test with rate limit error - should be handled by context manager
        response = await client.make_request("/user", simulate_rate_limit=True)

        # Should return None because context manager handled the rate limit but didn't retry
        assert response is None

        # Rate limiter should be paused
        assert client.rate_limiter.is_paused()

        # Verify sleep was called (may be called multiple times)
        assert mock_sleep.call_count >= 1
        # Check that one of the calls was with the expected backoff time
        assert any(call.args[0] == 5.1 for call in mock_sleep.call_args_list)

        # Reset mock
        mock_sleep.reset_mock()

        # Should be able to make requests again (but will sleep due to pause)
        response = await client.make_request("/user")
        assert response.status_code == 200

        # Should have called sleep again because pause is still active
        assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_context_manager_re_raises_non_rate_limit_errors(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that context manager re-raises non-rate-limit errors."""

        class ErrorMockGitHubClient(MockGitHubClient):
            async def make_request(
                self, resource: str, simulate_rate_limit: bool = False
            ) -> httpx.Response:
                async with self.rate_limiter:
                    self.request_count += 1

                    if simulate_rate_limit and self.request_count == 1:
                        # Simulate a non-rate-limit error (404)
                        mock_response = Mock()
                        mock_response.status_code = 404
                        mock_response.headers = {}
                        raise httpx.HTTPStatusError(
                            "Not found", request=Mock(), response=mock_response
                        )

                    # Simulate successful response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.headers = {
                        "x-ratelimit-limit": "1000",
                        "x-ratelimit-remaining": "999",
                        "x-ratelimit-reset": str(int(time.time()) + 3600),
                    }

                    self.rate_limiter.update_rate_limits(
                        httpx.Headers(mock_response.headers), resource
                    )
                    return mock_response

        client = ErrorMockGitHubClient(github_host, client_config)

        # Test with non-rate-limit error - should be re-raised
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.make_request("/user", simulate_rate_limit=True)

        # Should be a 404 error, not a rate limit error
        assert exc_info.value.response.status_code == 404

        # Rate limiter should not be paused for non-rate-limit errors
        assert not client.rate_limiter.is_paused()

        # Should not have called sleep for non-rate-limit errors
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_manager_handles_successful_requests(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that context manager handles successful requests without sleeping."""
        client = MockGitHubClient(github_host, client_config)

        # Make a successful request
        response = await client.make_request("/user")

        # Should succeed
        assert response.status_code == 200

        # Rate limiter should not be paused
        assert not client.rate_limiter.is_paused()

        # Should not have called sleep for successful requests
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_api_types_have_separate_limits(
        self, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that different API types have separate rate limits."""
        # Create different client configurations
        rest_config = GitHubRateLimiterConfig(
            api_type="rest", max_retries=3, max_concurrent=5
        )
        graphql_config = GitHubRateLimiterConfig(
            api_type="graphql", max_retries=2, max_concurrent=3
        )

        rest_client = MockGitHubClient(github_host, rest_config)
        graphql_client = MockGitHubClient(github_host, graphql_config)

        # Make requests to both APIs
        rest_response = await rest_client.make_request("/user")
        graphql_response = await graphql_client.make_request("/graphql")

        assert rest_response.status_code == 200
        assert graphql_response.status_code == 200

        # Check that they have separate rate limit info
        rest_status = rest_client.rate_limiter.get_rate_limit_status()
        graphql_status = graphql_client.rate_limiter.get_rate_limit_status()

        assert "rest" in rest_status
        assert "graphql" in graphql_status
        assert rest_status["rest"]["remaining"] == 999
        assert graphql_status["graphql"]["remaining"] == 999

    @pytest.mark.asyncio
    async def test_concurrency_limits_are_respected(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test that concurrency limits are properly enforced."""
        client = MockGitHubClient(github_host, client_config)

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent_seen = 0

        async def slow_request() -> httpx.Response:
            nonlocal concurrent_count, max_concurrent_seen
            concurrent_count += 1
            max_concurrent_seen = max(max_concurrent_seen, concurrent_count)

            # Simulate slow request (mocked sleep)
            await asyncio.sleep(0.01)

            concurrent_count -= 1
            return await client.make_request("/slow-endpoint")

        # Create more tasks than the concurrency limit
        tasks = []
        for i in range(client_config.max_concurrent * 2):
            task = asyncio.create_task(slow_request())
            tasks.append(task)

        # All should complete successfully
        responses = await asyncio.gather(*tasks)
        assert len(responses) == client_config.max_concurrent * 2
        assert all(response.status_code == 200 for response in responses)

        # Should never exceed max_concurrent
        assert max_concurrent_seen <= client_config.max_concurrent

        # Verify sleep was called for each request
        assert mock_sleep.call_count == client_config.max_concurrent * 2

    @pytest.mark.asyncio
    async def test_rate_limit_with_different_backoff_times(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test rate limiting with different backoff times."""
        # Test with different Retry-After values
        test_cases = [
            ("0.1", 5.1),  # 0.1 + 5 second buffer
            ("60", 65.0),  # 60 + 5 second buffer
            ("120", 125.0),  # 120 + 5 second buffer
        ]

        for retry_after, expected_backoff in test_cases:
            # Reset mock
            mock_sleep.reset_mock()

            # Create a custom client that returns specific Retry-After
            class CustomMockGitHubClient(MockGitHubClient):
                async def make_request(
                    self, resource: str, simulate_rate_limit: bool = False
                ) -> httpx.Response:
                    async with self.rate_limiter:
                        self.request_count += 1

                        if simulate_rate_limit and self.request_count == 1:
                            mock_response = Mock()
                            mock_response.status_code = 429
                            mock_response.headers = {"Retry-After": retry_after}
                            raise httpx.HTTPStatusError(
                                "Rate limited", request=Mock(), response=mock_response
                            )

                        # Simulate successful response
                        mock_response = Mock()
                        mock_response.status_code = 200
                        mock_response.headers = {
                            "x-ratelimit-limit": "1000",
                            "x-ratelimit-remaining": "999",
                            "x-ratelimit-reset": str(int(time.time()) + 3600),
                        }

                        self.rate_limiter.update_rate_limits(
                            httpx.Headers(mock_response.headers), resource
                        )
                        return mock_response

            custom_client = CustomMockGitHubClient(github_host, client_config)

            # Trigger rate limit - should be handled by context manager
            response = await custom_client.make_request(
                "/user", simulate_rate_limit=True
            )

            # Should return None because context manager handled the rate limit but didn't retry
            assert response is None

            # Verify correct backoff time was used (may be called multiple times)
            assert mock_sleep.call_count >= 1
            # Check that one of the calls was with the expected backoff time
            assert any(
                call.args[0] == expected_backoff for call in mock_sleep.call_args_list
            )

    @pytest.mark.asyncio
    async def test_http_client_retry_logic_with_rate_limiter(
        self, client_config: GitHubRateLimiterConfig, github_host: str, mock_sleep: Mock
    ) -> None:
        """Test how real HTTP clients would implement retry logic with rate limiter."""

        class RealisticMockGitHubClient(MockGitHubClient):
            async def make_request_with_retry(
                self, resource: str, max_retries: int = 3
            ) -> httpx.Response:
                """Simulate how real HTTP clients would handle rate limiting with retries."""
                for attempt in range(max_retries + 1):
                    try:
                        response = await self.make_request(
                            resource, simulate_rate_limit=(attempt == 0)
                        )

                        # If we get a response, the request succeeded
                        if response is not None:
                            return response

                        # If we get None, the rate limiter handled the error but didn't retry
                        # In a real client, we would retry the request
                        if attempt < max_retries:
                            # Wait a bit before retrying (in real code, this might be exponential backoff)
                            await asyncio.sleep(0.01)
                            continue
                        else:
                            # Max retries exceeded
                            raise httpx.HTTPStatusError(
                                "Max retries exceeded",
                                request=Mock(),
                                response=Mock(status_code=429),
                            )

                    except httpx.HTTPStatusError as e:
                        # If it's not a rate limit error, re-raise immediately
                        if e.response.status_code not in [403, 429]:
                            raise

                        # For rate limit errors, let the context manager handle them
                        # and retry if we haven't exceeded max retries
                        if attempt < max_retries:
                            await asyncio.sleep(0.01)
                            continue
                        else:
                            raise

                # This should never be reached, but mypy requires a return statement
                raise httpx.HTTPStatusError(
                    "Unexpected end of retry loop",
                    request=Mock(),
                    response=Mock(status_code=500),
                )

        client = RealisticMockGitHubClient(github_host, client_config)

        # First attempt should hit rate limit and return None
        response = await client.make_request("/user", simulate_rate_limit=True)
        assert response is None

        # Rate limiter should be paused
        assert client.rate_limiter.is_paused()

        # Verify sleep was called for rate limit handling (may be called multiple times)
        assert mock_sleep.call_count >= 1
        # Check that one of the calls was with the expected backoff time
        assert any(call.args[0] == 5.1 for call in mock_sleep.call_args_list)

        # Reset mock
        mock_sleep.reset_mock()

        # Now test the retry logic
        response = await client.make_request_with_retry("/user", max_retries=2)

        # Should eventually succeed
        assert response.status_code == 200

        # Should have called sleep for the retry delay
        assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_rate_limit_pause_blocks_other_coroutines(
        self, mock_sleep: Mock, github_host: str
    ) -> None:
        config = GitHubRateLimiterConfig(
            api_type="rest", max_concurrent=5, max_retries=0
        )
        limiter = GitHubRateLimiterRegistry.get_limiter(github_host, config)

        block_order = []

        async def rate_limited_task(
            name: str, delay_before_enter: float = 0, trigger_rate_limit: bool = False
        ) -> None:
            await asyncio.sleep(delay_before_enter)
            block_order.append(f"{name}-enter")

            try:
                async with limiter:
                    block_order.append(f"{name}-acquired")

                    if trigger_rate_limit:
                        mock_response = Mock()
                        mock_response.status_code = 429
                        mock_response.headers = {"Retry-After": "0.1"}
                        raise httpx.HTTPStatusError(
                            "Rate limited", request=Mock(), response=mock_response
                        )

                    await asyncio.sleep(0.01)
            except httpx.HTTPStatusError:
                block_order.append(f"{name}-rate-limited")
            block_order.append(f"{name}-exit")

        task_a = asyncio.create_task(
            rate_limited_task("A", delay_before_enter=0, trigger_rate_limit=True)
        )
        task_b = asyncio.create_task(rate_limited_task("B", delay_before_enter=0.001))

        await asyncio.gather(task_a, task_b)

        idx_acquire_a = block_order.index("A-acquired")
        idx_exit_a = block_order.index("A-exit")
        idx_acquire_b = block_order.index("B-acquired")

        # The key assertion
        assert idx_acquire_b > idx_exit_a  # B only gets in after A's pause finishes
        assert idx_acquire_a < idx_acquire_b  # A acquires before B

        # Sleep was called (means pause activated)
        assert mock_sleep.call_count >= 1
        assert any(call.args[0] >= 5.0 for call in mock_sleep.call_args_list)
