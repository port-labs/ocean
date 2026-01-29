import asyncio
from typing import Optional, Any, Type
import httpx
from loguru import logger
from gitlab.clients.rate_limiter.utils import (
    GitLabRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
)


class GitLabRateLimiter:
    def __init__(self, config: GitLabRateLimiterConfig) -> None:
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._block_lock = asyncio.Lock()

    async def __aenter__(self) -> "GitLabRateLimiter":
        await self._semaphore.acquire()

        async with self._block_lock:
            if self.rate_limit_info and (self.rate_limit_info.remaining <= 1):
                delay = self.rate_limit_info.seconds_until_reset
                if delay > 0:
                    logger.warning(
                        f"GitLab rate limit low ({self.rate_limit_info.remaining} remaining), "
                        f"pausing for {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self._semaphore.release()

    def _parse_rate_limit_headers(
        self, headers: RateLimiterRequiredHeaders
    ) -> Optional[RateLimitInfo]:
        if not (
            headers.ratelimit_limit
            and headers.ratelimit_remaining
            and headers.ratelimit_reset
        ):
            return None

        return RateLimitInfo(
            limit=int(headers.ratelimit_limit),
            remaining=int(headers.ratelimit_remaining),
            reset_time=int(headers.ratelimit_reset),
        )

    def update_rate_limits(
        self, headers: httpx.Headers, resource: str
    ) -> Optional[RateLimitInfo]:
        rate_limit_headers = RateLimiterRequiredHeaders(**dict(headers))

        info = self._parse_rate_limit_headers(rate_limit_headers)
        if info:
            self.rate_limit_info = info
            logger.debug(
                f"GitLab rate limit on {resource}: {info.remaining}/{info.limit} remaining"
            )
        return info

    def log_rate_limit_status(self) -> None:
        info = self.rate_limit_info
        if info:
            logger.debug(
                f"GitLab: {info.remaining}/{info.limit} remaining "
                f"({info.utilization_percentage:.1f}% used) - "
                f"resets in {info.seconds_until_reset}s"
            )
