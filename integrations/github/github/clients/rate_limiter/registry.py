from typing import Dict
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
