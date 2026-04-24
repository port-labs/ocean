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
        self._max_concurrent = config.max_concurrent
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._block_lock = asyncio.Lock()

    async def __aenter__(self) -> "GitLabRateLimiter":
        await self._semaphore.acquire()

        async with self._block_lock:
            # Pause when remaining requests <= max concurrent to account for in-flight requests
            if self.rate_limit_info and (
                self.rate_limit_info.remaining <= self._max_concurrent
            ):
                delay = self.rate_limit_info.seconds_until_reset
                if delay > 0:
                    logger.warning(
                        f"GitLab rate limit is running low: {self.rate_limit_info.remaining} requests left. "
                        f"Max concurrency is {self._max_concurrent}. Pausing for {delay:.1f} seconds."
                    )
                    await asyncio.sleep(delay)
                    self.rate_limit_info = None  # Reset after pause

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
                f"GitLab rate limit: {info.remaining} of {info.limit} requests remaining "
                f"({info.utilization_percentage:.1f}% used). "
                f"Resets in {info.seconds_until_reset} seconds."
            )
