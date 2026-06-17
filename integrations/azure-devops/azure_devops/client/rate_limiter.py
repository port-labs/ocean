import asyncio
import time
from typing import Any, Optional, Type

import httpx
from loguru import logger

LIMIT_HEADER = "x-ratelimit-limit"
LIMIT_REMAINING_HEADER = "x-ratelimit-remaining"
LIMIT_RESET_HEADER = "x-ratelimit-reset"
LIMIT_RETRY_AFTER_HEADER = "retry-after"


class AzureDevOpsRateLimiter:
    """Rate limiter for Azure DevOps API requests.

    Manages concurrent requests and respects Azure DevOps rate limiting headers
    to prevent hitting API limits. Uses semaphore for concurrency control and
    proactively waits when approaching rate limits.

    Reference: https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rate-limits?view=azure-devops
    """

    def __init__(self, max_concurrent: int = 15, minimum_limit_remaining: int = 1):
        """
        Initialize the Azure DevOps rate limiter.

        Args:
            max_concurrent: Maximum number of concurrent in-flight requests.
            minimum_limit_remaining: Proactively sleep if remaining requests fall
                below this threshold to avoid hitting rate limits.
        """
        self._minimum_limit_remaining = minimum_limit_remaining
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        # Rate limit state - only set when headers are present
        self._limit: Optional[int] = None
        self._remaining: Optional[int] = None
        self._reset_time: Optional[float] = None

        # Throttle signal set on timeout - no headers available to read reset time
        self._throttle_until: Optional[float] = None

    @property
    def seconds_until_reset(self) -> float:
        """Calculate seconds until rate limit window resets.

        Returns:
            Seconds remaining until reset, or 0.0 if no reset time is set.
        """
        if self._reset_time is not None:
            return max(0.0, self._reset_time - time.time())
        return 0.0

    @property
    def should_wait_for_retry_after(self) -> float:
        """Calculate wait time based on rate limit reset time.

        Returns:
            Seconds to wait, or 0.0 if no wait is needed.
        """
        if self._reset_time is not None:
            wait_time = self._reset_time - time.time()
            return max(0.0, wait_time)
        return 0.0

    async def signal_throttle(self, seconds: float) -> None:
        """Signal a throttle event — pause all subsequent requests for the given duration.

        Used when throttling manifests as a timeout (no response headers available).
        """
        async with self._lock:
            throttle_end_time = time.time() + seconds
            if self._throttle_until is None or throttle_end_time > self._throttle_until:
                self._throttle_until = throttle_end_time
                logger.warning(
                    f"ADO rate limit: ReadTimeout detected, pausing all requests for {seconds:.0f} seconds"
                )
            else:
                logger.debug(
                    f"ADO rate limit: ReadTimeout received but existing throttle window already covers it "
                    f"(expires in {self._throttle_until - time.time():.0f}s)"
                )

    async def __aenter__(self) -> "AzureDevOpsRateLimiter":
        """Enter the async context manager.

        Acquires semaphore and handles rate limiting logic before allowing request.
        """
        await self._semaphore.acquire()

        async with self._lock:
            # Check shared throttle signal from ReadTimeout (no headers)
            if self._throttle_until is not None:
                remaining_seconds = self._throttle_until - time.time()
                if remaining_seconds > 0:
                    logger.warning(
                        f"ADO rate limit: holding request for {remaining_seconds:.0f} seconds while throttle window expires"
                    )
                    await asyncio.sleep(remaining_seconds)
                else:
                    logger.debug(
                        "ADO rate limit: throttle window already expired, clearing and proceeding"
                    )
                self._throttle_until = None

            # Check if we need to wait due to previous rate limit
            retry_wait = self.should_wait_for_retry_after
            if retry_wait > 0:
                logger.debug(
                    f"Rate limit: waiting {retry_wait:.2f}s due to previous rate limit"
                )
                await asyncio.sleep(retry_wait)
                self._reset_rate_limit_state()

            # Proactively wait if remaining requests are low (separate check)
            if (
                self._remaining is not None
                and self._remaining <= self._minimum_limit_remaining
            ):
                reset_wait = self.seconds_until_reset
                if reset_wait > 0:
                    logger.debug(
                        f"Rate limit: proactively waiting {reset_wait:.2f}s "
                        f"(remaining: {self._remaining}, threshold: {self._minimum_limit_remaining})"
                    )
                    await asyncio.sleep(reset_wait)
                    self._reset_rate_limit_state()

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit the async context manager.

        Releases the semaphore to allow other requests to proceed.
        """
        self._semaphore.release()

    def _reset_rate_limit_state(self) -> None:
        """Reset all rate limit state variables."""
        self._limit = None
        self._remaining = None
        self._reset_time = None

    async def update_from_headers(self, headers: httpx.Headers) -> None:
        """
        Update internal rate limit status from Azure DevOps response headers.

        Azure DevOps rate limit headers are only present when approaching limits:
        - X-RateLimit-Limit: Total TSTUs (Team Services Time Units) allowed
        - X-RateLimit-Remaining: TSTUs remaining in current window
        - X-RateLimit-Reset: Unix timestamp when usage returns to 0

        Args:
            headers: HTTP response headers from Azure DevOps API
        """
        async with self._lock:
            try:
                limit_header = headers.get(LIMIT_HEADER)
                remaining_header = headers.get(LIMIT_REMAINING_HEADER)
                reset_header = headers.get(LIMIT_RESET_HEADER)

                # Update limit and remaining if both are present
                if limit_header and remaining_header:
                    self._limit = int(limit_header)
                    self._remaining = int(remaining_header)
                    logger.debug(
                        f"Rate limit updated - Remaining: {self._remaining}/{self._limit} TSTUs"
                    )

                # Update reset time if present
                if reset_header:
                    self._reset_time = float(reset_header)
                    logger.debug(
                        f"Rate limit resets at {self._reset_time} "
                        f"(in {self.seconds_until_reset:.2f}s)"
                    )

                # Log comprehensive status if any rate limit info is present
                if any([limit_header, remaining_header, reset_header]):
                    remaining_str = (
                        f"{self._remaining}"
                        if self._remaining is not None
                        else "unknown"
                    )
                    limit_str = (
                        f"{self._limit}" if self._limit is not None else "unknown"
                    )
                    reset_str = (
                        f"{self.seconds_until_reset:.1f}s"
                        if self._reset_time
                        else "unknown"
                    )

                    logger.debug(
                        f"Rate limit status - Remaining: {remaining_str}/{limit_str} TSTUs, "
                        f"resets in: {reset_str}"
                    )

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse Azure DevOps rate limit headers: {e}.")
