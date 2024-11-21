from aiolimiter import AsyncLimiter

_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0
_PERCENTAGE_OF_QUOTA: float = 0.2
_DEFAULT_RATE_LIMIT_QUOTA: int = 60


class GitLabRateLimiter:
    def __init__(
            self,
            quota: int = _DEFAULT_RATE_LIMIT_QUOTA,
            time_period: float = _DEFAULT_RATE_LIMIT_TIME_PERIOD,
            percentage: float = _PERCENTAGE_OF_QUOTA
    ):
        effective_quota_limit = int(max(round(quota * percentage, 1), 1))
        self.limiter = AsyncLimiter(max_rate=effective_quota_limit, time_period=time_period)

    async def get_limiter(self) -> AsyncLimiter:
        return self.limiter
