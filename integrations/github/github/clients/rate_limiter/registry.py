from typing import Dict, Optional
from threading import Lock


from github.clients.rate_limiter.limiter import GitHubRateLimiter
from github.clients.rate_limiter.utils import GitHubRateLimiterConfig


class GitHubRateLimiterRegistry:
    _instances: Dict[str, GitHubRateLimiter] = {}
    _lock = Lock()

    @classmethod
    def get_limiter(
        cls, host: str, config: GitHubRateLimiterConfig
    ) -> GitHubRateLimiter:
        key = f"{host}:{config.api_type}"

        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = GitHubRateLimiter(config)
            return cls._instances[key]

    @classmethod
    def get_limiter_if_exists(
        cls, host: str, api_type: str
    ) -> Optional[GitHubRateLimiter]:
        """Return an existing rate limiter if one was created for this host and api_type."""
        key = f"{host}:{api_type}"
        with cls._lock:
            return cls._instances.get(key)
