import asyncio
import time
from typing import Optional, Type, Any

import httpx
from loguru import logger


class SentryRateLimiter:
    """
    Orchestrates Sentry API requests to handle rate limits gracefully.

    This class provides a context manager to handle rate-limiting. It inspects
    Sentry's rate-limiting headers on each response and introduces delays to
    prevent hitting the rate limit. It handles both proactive (based on
    X-Sentry-Rate-Limit-Remaining) and reactive (based on 429 Too Many Requests
    with a Retry-After header) rate limiting.

    Sentry Rate Limit Headers:
    - X-Sentry-Rate-Limit-Limit: The total number of requests allowed in the window.
    - X-Sentry-Rate-Limit-Remaining: The number of requests remaining in the window.
    - X-Sentry-Rate-Limit-Reset: The UTC epoch timestamp when the window resets.

    For more information, see: https://docs.sentry.io/api/ratelimits/
    and https://develop.sentry.dev/sdk/expected-features/rate-limiting/

Usage:
    limiter = SentryRateLimiter(max_concurrent=5, minimum_limit_remaining=1)
    
    async with limiter:
        response = await client.request(method, url, **kwargs)
        await limiter.update_from_headers(response.headers)

Parameters:
    max_concurrent: Maximum number of concurrent requests (default: 5)
    minimum_limit_remaining: Proactively sleep if remaining requests fall
        below this number (default: 1)

    """

    def __init__(
        self,
        max_concurrent: int = 5,
        minimum_limit_remaining: int = 1,
    ) -> None:
        """
        Initializes the SentryRateLimiter.

        Args:
            max_concurrent: Max number of concurrent in-flight requests.
            minimum_limit_remaining: Proactively sleep if remaining requests fall
                below this number.
        """
        self._minimum_limit_remaining = minimum_limit_remaining

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        self._limit: Optional[int] = None
        self._remaining: Optional[int] = None
        self._reset_time: Optional[float] = None

    @property
    def seconds_until_reset(self) -> float:
        """Calculates the time in seconds until the rate limit window resets."""
        if self._reset_time:
            return self._reset_time - time.time()
        logger.debug("Rate limit reset time is not set")
        return 0.0

    async def __aenter__(self) -> "SentryRateLimiter":
        """Acquires semaphore and proactively sleeps if the rate limit is low."""
        await self._semaphore.acquire()

        async with self._lock:
            if self._remaining and self._remaining <= self._minimum_limit_remaining:
                sleep_duration = self.seconds_until_reset
                if sleep_duration > 0:
                    logger.debug(
                        f"Proactively sleeping for {sleep_duration:.2f}s as rate limit "
                        f"remaining ({self._remaining}) is near threshold "
                        f"({self._minimum_limit_remaining})."
                    )
                    await asyncio.sleep(sleep_duration)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """
        Ensuring the semaphore is always released
        """
        self._semaphore.release()

    async def update_from_headers(self, headers: httpx.Headers) -> None:
        """
        Updates the internal rate limit status from response headers.
        """
        async with self._lock:
            try:
                limit = headers.get("X-Sentry-Rate-Limit-Limit")
                remaining = headers.get("X-Sentry-Rate-Limit-Remaining")
                reset_seconds = headers.get("X-Sentry-Rate-Limit-Reset")

                if limit and remaining and reset_seconds:
                    self._limit = int(limit)
                    self._remaining = int(remaining)
                    self._reset_time = float(reset_seconds)
                    logger.debug(
                        f"Sentry rate limit updated. "
                        f"Remaining: {self._remaining}. "
                        f"Limit: {self._limit}. "
                        f"Resets in {max(0.0, self.seconds_until_reset):.2f}s."
                    )

            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse Sentry rate limit headers: {e}")
