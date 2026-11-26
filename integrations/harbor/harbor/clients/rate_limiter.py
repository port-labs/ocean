import asyncio
import time
from typing import Optional, Any, Type

import httpx
from loguru import logger
from pydantic import BaseModel, Field


class RateLimitHeaders(BaseModel):
    """Headers required for rate limit tracking."""

    x_ratelimit_limit: Optional[str] = Field(default=None, alias="x-ratelimit-limit")
    x_ratelimit_remaining: Optional[str] = Field(default=None, alias="x-ratelimit-remaining")
    x_ratelimit_reset: Optional[str] = Field(default=None, alias="x-ratelimit-reset")

    class Config:
        populate_by_name = True


class RateLimitInfo(BaseModel):
    """Information about current rate limit status."""

    remaining: int
    reset_time: int
    limit: int

    @property
    def seconds_until_reset(self) -> float:
        return max(0, self.reset_time - time.time())

    @property
    def utilization_percentage(self) -> float:
        if self.limit == 0:
            return 0
        return ((self.limit - self.remaining) / self.limit) * 100


class HarborRateLimiter:
    """
    Rate limiter for Harbor API requests.

    Implements concurrency control via semaphore and automatic waiting
    when rate limits are approached. Uses Harbor's rate limit headers:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
    """

    def __init__(self, max_concurrent: int = 10) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._block_lock = asyncio.Lock()
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self.max_concurrent = max_concurrent

    async def __aenter__(self) -> "HarborRateLimiter":
        await self._semaphore.acquire()

        async with self._block_lock:
            if self.rate_limit_info and self.rate_limit_info.remaining <= 1:
                delay = self.rate_limit_info.seconds_until_reset
                if delay > 0:
                    logger.warning(f"Harbor API rate limit approaching, pausing for {delay:.1f}s")
                    await asyncio.sleep(delay)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self._semaphore.release()

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        """Check if response indicates rate limiting."""
        if response.status_code != 429:
            return False
        return True

    def _parse_rate_limit_headers(self, headers: RateLimitHeaders) -> Optional[RateLimitInfo]:
        """Parse rate limit headers into RateLimitInfo."""
        if not (headers.x_ratelimit_limit and headers.x_ratelimit_remaining and headers.x_ratelimit_reset):
            return None

        try:
            return RateLimitInfo(
                limit=int(headers.x_ratelimit_limit),
                remaining=int(headers.x_ratelimit_remaining),
                reset_time=int(headers.x_ratelimit_reset),
            )
        except ValueError:
            return None

    def update_rate_limits(self, headers: httpx.Headers, endpoint: str) -> Optional[RateLimitInfo]:
        """Update rate limit info from response headers."""
        rate_limit_headers = RateLimitHeaders(**dict(headers))
        info = self._parse_rate_limit_headers(rate_limit_headers)

        if info:
            self.rate_limit_info = info
            if info.remaining <= 5:
                logger.debug(f"Harbor rate limit on {endpoint}: {info.remaining}/{info.limit} remaining")

        return info

    def log_rate_limit_status(self) -> None:
        """Log current rate limit status for debugging."""
        if self.rate_limit_info:
            logger.info(
                f"Harbor rate limit status: {self.rate_limit_info.remaining}/{self.rate_limit_info.limit} "
                f"remaining, resets in {self.rate_limit_info.seconds_until_reset:.1f}s"
            )
        else:
            logger.info("Harbor rate limit status: No rate limit info available")
