from typing import Generator

import pytest

from gitlab.clients.rate_limiter.limiter import GitLabRateLimiter
from gitlab.clients.rate_limiter.registry import GitLabRateLimiterRegistry
from gitlab.clients.rate_limiter.utils import GitLabRateLimiterConfig


@pytest.fixture(autouse=True)
def clear_registry() -> Generator[None, None, None]:
    """Clear the registry before and after each test."""
    GitLabRateLimiterRegistry.clear()
    yield
    GitLabRateLimiterRegistry.clear()


@pytest.fixture
def config() -> GitLabRateLimiterConfig:
    """Create a default rate limiter config."""
    return GitLabRateLimiterConfig(max_concurrent=10)


@pytest.fixture
def gitlab_host() -> str:
    """Provide a test GitLab host."""
    return "https://gitlab.example.com"


class TestGitLabRateLimiterRegistry:
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
        # Create some limiters
        GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)
        GitLabRateLimiterRegistry.get_limiter("https://other.gitlab.com", config)

        # Clear registry
        GitLabRateLimiterRegistry.clear()

        # New call should create fresh instance
        limiter_after = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        # Verify it's a new instance (registry was cleared)
        assert len(GitLabRateLimiterRegistry._instances) == 1

    def test_limiter_uses_provided_config(
        self, gitlab_host: str
    ) -> None:
        """Test that limiter is created with provided config."""
        config = GitLabRateLimiterConfig(max_concurrent=25)

        limiter = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        assert limiter._max_concurrent == 25

    def test_second_call_ignores_different_config(
        self, gitlab_host: str
    ) -> None:
        """Test that subsequent calls for same host ignore different config."""
        config1 = GitLabRateLimiterConfig(max_concurrent=10)
        config2 = GitLabRateLimiterConfig(max_concurrent=50)

        limiter1 = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config1)
        limiter2 = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config2)

        # Same instance returned
        assert limiter1 is limiter2
        # Config from first call is used
        assert limiter1._max_concurrent == 10

    @pytest.mark.asyncio
    async def test_shared_limiter_tracks_rate_limits_across_clients(
        self, gitlab_host: str, config: GitLabRateLimiterConfig
    ) -> None:
        """Test that shared limiter properly tracks rate limits."""
        limiter1 = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)
        limiter2 = GitLabRateLimiterRegistry.get_limiter(gitlab_host, config)

        # Update rate limits via first limiter
        import time
        import httpx

        headers = httpx.Headers(
            {
                "ratelimit-limit": "60",
                "ratelimit-remaining": "45",
                "ratelimit-reset": str(int(time.time()) + 60),
            }
        )
        limiter1.update_rate_limits(headers)

        # Second limiter should see the same rate limit info
        assert limiter2.rate_limit_info is not None
        assert limiter2.rate_limit_info.remaining == 45
