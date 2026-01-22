import asyncio
from typing import Any, Optional, Type

import httpx
from loguru import logger

from gitlab.clients.rate_limiter.utils import (
    GitLabRateLimiterConfig,
    RateLimitInfo,
    RateLimiterRequiredHeaders,
    has_exhausted_rate_limit_headers,
)


class GitLabRateLimiter:
    """
    Rate limiter for GitLab API requests.

    Provides:
    - Semaphore-based concurrency control
    - Proactive pausing when rate limit is low
    - Response header tracking for rate limit state

    Usage:
        async with rate_limiter:
            response = await client.request(...)
            rate_limiter.update_rate_limits(response.headers)
    """

    def __init__(self, config: GitLabRateLimiterConfig) -> None:
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._max_concurrent = config.max_concurrent
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._block_lock = asyncio.Lock()

    async def __aenter__(self) -> "GitLabRateLimiter":
        """Acquire semaphore and check if we should proactively pause."""
        logger.info(f"Rate limiter: acquiring semaphore (max_concurrent={self._max_concurrent})")
        await self._semaphore.acquire()

        async with self._block_lock:
            # Proactive: pause if remaining requests <= max_concurrent
            # This prevents multiple concurrent requests from all hitting the limit
            if self.rate_limit_info and (
                self.rate_limit_info.remaining <= self._max_concurrent
            ):
                delay = self.rate_limit_info.seconds_until_reset
                if delay > 0:
                    logger.warning(
                        f"GitLab rate limit low ({self.rate_limit_info.remaining} remaining), "
                        f"pausing for {delay}s until reset"
                    )
                    await asyncio.sleep(delay)
                    # Reset rate limit info after waiting
                    self.rate_limit_info = None

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Release semaphore."""
        self._semaphore.release()

    def is_rate_limit_response(self, response: httpx.Response) -> bool:
        """
        Check if response indicates rate limiting.

        Args:
            response: HTTP response to check

        Returns:
            True if response is a rate limit error (429 or 403 with exhausted headers)
        """
        if response.status_code == 429:
            return True
        # GitLab may return 403 for rate limits in some cases
        if response.status_code == 403:
            return has_exhausted_rate_limit_headers(response.headers)
        return False

    def update_rate_limits(self, headers: httpx.Headers) -> Optional[RateLimitInfo]:
        """
        Update rate limit tracking from response headers.

        Args:
            headers: Response headers from GitLab API

        Returns:
            Updated RateLimitInfo if headers present, None otherwise
        """
        try:
            rate_headers = RateLimiterRequiredHeaders(**dict(headers))

            if not (rate_headers.ratelimit_remaining and rate_headers.ratelimit_reset):
                return None

            self.rate_limit_info = RateLimitInfo(
                limit=int(rate_headers.ratelimit_limit or 0),
                remaining=int(rate_headers.ratelimit_remaining),
                reset_time=int(rate_headers.ratelimit_reset),
            )

            logger.info(
                f"GitLab rate limit: {self.rate_limit_info.remaining}/{self.rate_limit_info.limit} "
                f"remaining ({self.rate_limit_info.utilization_percentage:.1f}% used), "
                f"resets in {self.rate_limit_info.seconds_until_reset}s"
            )

            return self.rate_limit_info

        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse rate limit headers: {e}")
            return None
