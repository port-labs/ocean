import asyncio
from aiolimiter import AsyncLimiter
from loguru import logger

_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0
_PERCENTAGE_OF_QUOTA: float = 0.2
_DEFAULT_RATE_LIMIT_QUOTA: int = 60


class GitLabRateLimiter:
    def __init__(
        self,
        quota: int = _DEFAULT_RATE_LIMIT_QUOTA,
        time_period: float = _DEFAULT_RATE_LIMIT_TIME_PERIOD,
        percentage: float = _PERCENTAGE_OF_QUOTA,
    ):
        effective_quota_limit = int(max(round(quota * percentage, 1), 1))
        self.time_period = time_period
        self.limiter = AsyncLimiter(
            max_rate=effective_quota_limit, time_period=time_period
        )

    async def handle_rate_limit_headers(self, response_headers: dict) -> None:
        """
        Adjusts the rate limiter based on GitLab's rate-limit response headers.

        :param response_headers: Dictionary of response headers from GitLab API.
        """
        rate_limit = response_headers.get("RateLimit-Limit")
        rate_remaining = response_headers.get("RateLimit-Remaining")
        rate_reset = response_headers.get("RateLimit-Reset")

        try:
            if rate_limit and rate_remaining and rate_reset:
                rate_limit = int(rate_limit)
                rate_remaining = int(rate_remaining)
                rate_reset = int(rate_reset)

                logger.info(
                    f"Rate limit details: Limit={rate_limit}, Remaining={rate_remaining}, Reset={rate_reset}"
                )

                # Adjust the limiter's max rate and time period based on headers
                self.limiter.max_rate = rate_limit
                self.limiter.time_period = rate_reset - asyncio.get_event_loop().time()
                self.limiter._time_period = self.time_period
        except ValueError as e:
            logger.error(f"Error parsing rate-limit headers: {e}")
