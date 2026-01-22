from typing import Dict
from threading import Lock

from gitlab.clients.rate_limiter.limiter import GitLabRateLimiter
from gitlab.clients.rate_limiter.utils import GitLabRateLimiterConfig


class GitLabRateLimiterRegistry:
    """
    Singleton registry for GitLabRateLimiter instances.

    Ensures one rate limiter per GitLab host to properly track
    rate limits across all requests to the same host.
    """

    _instances: Dict[str, GitLabRateLimiter] = {}
    _lock = Lock()

    @classmethod
    def get_limiter(
        cls, host: str, config: GitLabRateLimiterConfig
    ) -> GitLabRateLimiter:
        """
        Get or create a rate limiter for a GitLab host.

        Args:
            host: GitLab host URL
            config: Rate limiter configuration

        Returns:
            GitLabRateLimiter instance for the host
        """
        with cls._lock:
            if host not in cls._instances:
                cls._instances[host] = GitLabRateLimiter(config)
            return cls._instances[host]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered rate limiters. Useful for testing."""
        with cls._lock:
            cls._instances.clear()
