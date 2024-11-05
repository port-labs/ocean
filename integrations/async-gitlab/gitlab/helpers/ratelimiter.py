from typing import final
from aiolimiter import AsyncLimiter
from loguru import logger
from gitlab.helpers.quota import GitLabAPIQuota


_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0  # Time period in seconds
_PERCENTAGE_OF_QUOTA: float = 0.2  # Percentage of the quota to use

class GitLabRateLimiter(GitLabAPIQuota):
    """
    GitLabAPIRateLimiter manages rate limits for GitLab API requests.
    It inherits from GitLabAPIQuota and leverages a rate limiter to control the rate of API requests based on the specified quota.
    """

    time_period: float = _DEFAULT_RATE_LIMIT_TIME_PERIOD

    async def default_rate_limiter(self) -> AsyncLimiter:
        quota = int(max(round(self._default_quota * _PERCENTAGE_OF_QUOTA, 1), 1))
        logger.info(f"Using {quota} as the rate limit for API requests.")
        return AsyncLimiter(max_rate=quota, time_period=self.time_period)

    async def register(self) -> AsyncLimiter:
        quota = await self._get_quota()
        effective_quota_limit: int = int(max(round(quota * _PERCENTAGE_OF_QUOTA, 1), 1))
        logger.info(f"Effective quota limit for rate limiting: {effective_quota_limit}.")
        limiter = AsyncLimiter(max_rate=effective_quota_limit, time_period=self.time_period)
        return limiter

    @final
    def quota_name(self) -> str:
        return "GitLab API Rate Limit"

    async def limiter(self) -> AsyncLimiter:
        return await self.register()
