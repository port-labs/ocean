import asyncio
import time
from typing import Any, Optional, Type

import httpx
from loguru import logger

LIMIT_HEADER = "x-ratelimit-limit"
LIMIT_REMAINING_HEADER = "x-ratelimit-remaining"
LIMIT_RESET_HEADER = "x-ratelimit-reset"
LIMIT_RETRY_AFTER_HEADER = "retry-after"

MIN_REMAINING_BACKOFF_SECONDS = 0.25
MAX_RETRY_AFTER_WAIT_SECONDS = 30.0


class AzureDevOpsRateLimiter:
    """Rate limiter for Azure DevOps API requests.

    Waits on ``Retry-After`` (capped), applies a short smoothing delay when
    ``X-RateLimit-Remaining`` is low, and records ``X-RateLimit-Reset`` for
    logs only.
    """

    def __init__(self, max_concurrent: int = 15, minimum_limit_remaining: int = 1):
        """
        Initialize the Azure DevOps rate limiter.

        Args:
            max_concurrent: Maximum number of concurrent in-flight requests.
            minimum_limit_remaining: Smoothing delay threshold for remaining TSTUs.
        """
        self._minimum_limit_remaining = minimum_limit_remaining
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        # Rate limit state - only set when headers are present
        self._limit: Optional[int] = None
        self._remaining: Optional[int] = None
        self._reset_time: Optional[float] = None
        # Wall-clock time until the latest Retry-After expires; None if unset.
        self._retry_after_until: Optional[float] = None

    @property
    def seconds_until_reset(self) -> float:
        """Seconds until reset timestamp; for logging only, not used to gate requests."""
        if self._reset_time is not None:
            return max(0.0, self._reset_time - time.time())
        return 0.0

    async def __aenter__(self) -> "AzureDevOpsRateLimiter":
        """Acquire semaphore; wait on Retry-After or low-remaining smoothing if needed."""
        await self._semaphore.acquire()

        async with self._lock:
            remaining = self._remaining
            threshold = self._minimum_limit_remaining
            retry_after_wait = (
                max(0.0, self._retry_after_until - time.time())
                if self._retry_after_until is not None
                else 0.0
            )

        if retry_after_wait > 0:
            bounded_wait = min(retry_after_wait, MAX_RETRY_AFTER_WAIT_SECONDS)
            logger.debug(
                f"Rate limit: honoring Retry-After wait {bounded_wait:.2f}s "
                f"(requested: {retry_after_wait:.2f}s, "
                f"cap: {MAX_RETRY_AFTER_WAIT_SECONDS}s)"
            )
            await asyncio.sleep(bounded_wait)
        elif remaining is not None and remaining <= threshold:
            logger.debug(
                f"Rate limit: smoothing wait {MIN_REMAINING_BACKOFF_SECONDS}s "
                f"(remaining: {remaining}, threshold: {threshold})"
            )
            await asyncio.sleep(MIN_REMAINING_BACKOFF_SECONDS)

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
        """Reset all rate limit state variables. Used by tests."""
        self._limit = None
        self._remaining = None
        self._reset_time = None
        self._retry_after_until = None

    async def update_from_headers(self, headers: httpx.Headers) -> None:
        """Update rate-limit state from response headers.

        Uses pessimistic ``min`` for remaining and ``max`` for Retry-After when
        concurrent responses arrive out of order.

        Args:
            headers: HTTP response headers from the API.
        """
        async with self._lock:
            try:
                limit_header = headers.get(LIMIT_HEADER)
                remaining_header = headers.get(LIMIT_REMAINING_HEADER)
                reset_header = headers.get(LIMIT_RESET_HEADER)
                retry_after_header = headers.get(LIMIT_RETRY_AFTER_HEADER)

                if limit_header and remaining_header:
                    self._limit = int(limit_header)
                    incoming_remaining = int(remaining_header)
                    if self._remaining is None:
                        self._remaining = incoming_remaining
                    else:
                        self._remaining = min(self._remaining, incoming_remaining)
                    logger.debug(
                        f"Rate limit updated - Remaining: {self._remaining}/{self._limit} TSTUs"
                    )

                if reset_header:
                    self._reset_time = float(reset_header)
                    logger.debug(
                        f"Rate limit resets at {self._reset_time} "
                        f"(in {self.seconds_until_reset:.2f}s; telemetry only)"
                    )

                if retry_after_header:
                    retry_after_seconds = float(retry_after_header)
                    incoming_until = time.time() + retry_after_seconds
                    if self._retry_after_until is None:
                        self._retry_after_until = incoming_until
                    else:
                        self._retry_after_until = max(
                            self._retry_after_until, incoming_until
                        )
                    logger.debug(
                        f"Retry-After received: {retry_after_seconds:.2f}s; "
                        f"next request gated until {self._retry_after_until:.2f}"
                    )

                if any(
                    [limit_header, remaining_header, reset_header, retry_after_header]
                ):
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
