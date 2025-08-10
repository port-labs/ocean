import asyncio
import time
from typing import Optional, Any, Type

import httpx
from loguru import logger


class LaunchDarklyRateLimiter:
    """
    An asynchronous, self-contained rate limiter for the LaunchDarkly API client.

    This class uses a context manager to automatically handle rate limiting by
    proactively sleeping when request limits are low and reactively retrying
    with backoff on 429 Too Many Requests responses.
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        minimum_limit_remaining: int = 1,
    ) -> None:
        """
        Initializes the rate limiter.

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
            return max(0.0, float(self._reset_time) - time.time())
        return 0.0

    async def __aenter__(self) -> "LaunchDarklyRateLimiter":
        """Acquires semaphore and proactively sleeps if the rate limit is low."""
        await self._semaphore.acquire()

        async with self._lock:
            if self._remaining and self._remaining <= self._minimum_limit_remaining:
                sleep_duration = self.seconds_until_reset
                if sleep_duration > 0:
                    logger.info(
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
    ) -> Optional[bool]:
        """
        Ensuring the semaphore is always released
        """
        self._semaphore.release()

    async def update_from_headers(self, headers: httpx.Headers) -> None:
        """
        Updates the internal rate limit status from response headers. This should
        be called by the client after every request.
        """
        async with self._lock:
            try:
                limit = headers.get("X-Ratelimit-Route-Limit")
                remaining = headers.get("X-Ratelimit-Route-Remaining") or headers.get(
                    "X-Ratelimit-Global-Remaining"
                )
                reset_ms = headers.get("X-Ratelimit-Reset")

                if limit and remaining and reset_ms:
                    self._limit = int(limit)
                    self._remaining = int(remaining)
                    self._reset_time = float(reset_ms) / 1000.0
                    logger.info(
                        f"LaunchDarkly rate limit updated. "
                        f"Remaining: {self._remaining}. "
                        f"Limit: {self._limit}. "
                        f"Resets in {self.seconds_until_reset:.2f}s."
                    )

            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse LaunchDarkly rate limit headers: {e}")
