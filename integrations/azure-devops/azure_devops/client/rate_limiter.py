import asyncio
import time
from typing import Any, Optional, Type

import httpx
from loguru import logger


class AzureDevOpsRateLimiter:
    def __init__(self, max_concurrent: int = 15, minimum_limit_remaining: int = 1):
        """
        Initializes the AzureDevOpsRateLimiter
        https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rate-limits?view=azure-devops

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
            return max(0.0, self._reset_time - time.time())
        return 0.0

    @property
    def should_wait_for_retry_after(self) -> float:
        """Returns seconds to wait based on Retry-After header."""
        if self._reset_time:
            wait_time = self._reset_time - time.time()
            return max(0.0, wait_time)
        return 0.0

    async def __aenter__(self) -> "AzureDevOpsRateLimiter":
        """
        Acquire the semaphore when the context manager enters.
        """
        await self._semaphore.acquire()

        async with self._lock:
            retry_wait = self.should_wait_for_retry_after
            if retry_wait > 0:
                logger.debug(
                    f"Waiting {retry_wait:.2f}s due to previous Retry-After header"
                )
                await asyncio.sleep(retry_wait)
                self._reset_time = None

            elif (
                self._remaining is not None
                and self._remaining <= self._minimum_limit_remaining
            ):
                reset_wait = self.seconds_until_reset
                if reset_wait > 0:
                    logger.debug(
                        f"Proactively waiting {reset_wait:.2f}s as rate limit "
                        f"remaining ({self._remaining}) is low"
                    )
                    await asyncio.sleep(reset_wait)
                    self._limit = None
                    self._remaining = None
                    self._reset_time = None

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """
        Release the semaphore when the context manager exits.
        """
        self._semaphore.release()

    async def update_from_headers(self, headers: httpx.Headers) -> None:
        """
        Updates the internal rate limit status from response headers.

        Azure DevOps rate limit headers are only present when approaching limits:
        - X-RateLimit-Limit: Total TSTUs allowed
        - X-RateLimit-Remaining: TSTUs remaining
        - X-RateLimit-Reset: Time when usage returns to 0 (Unix timestamp in seconds)
        """
        async with self._lock:
            try:
                limit = headers.get("X-RateLimit-Limit")
                remaining = headers.get("X-RateLimit-Remaining")
                reset_time = headers.get("X-RateLimit-Reset")

                if limit and remaining:
                    self._limit = int(limit)
                    self._remaining = int(remaining)
                    logger.debug(
                        f"Rate limit info - Remaining: {self._remaining}, Limit: {self._limit}"
                    )

                if reset_time:
                    # X-RateLimit-Reset is typically a Unix timestamp in seconds
                    self._reset_time = float(reset_time)
                    logger.debug(
                        f"Rate limit resets at {self._reset_time} (in {self.seconds_until_reset:.2f}s)"
                    )

                # Log comprehensive rate limit status when headers are present
                if any([limit, remaining, reset_time]):
                    logger.debug(
                        f"Rate limit: {self._remaining}/{self._limit}, reset in {self.seconds_until_reset:.1f}s"
                    )

            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse AzureDevOps rate limit headers: {e}")
