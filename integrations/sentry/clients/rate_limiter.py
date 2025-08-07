import asyncio
import time
from typing import Optional, Type, Any, cast

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
        limiter = SentryRateLimiter()
        client = httpx.AsyncClient()
        async with limiter:
            response = await client.get("https://sentry.io/api/...")
    """

    def __init__(
        self,
        maximum_retries: int = 3,
        minimum_limit_remaining: int = 5,
        concurrent_requests: int = 10,
        maximum_sleep_duration: int = 5,
    ) -> None:
        """
        Initializes the SentryRateLimiter.

        Args:
            maximum_retries (int): The maximum number of times to retry a
                rate-limited request (429).
            minimum_limit_remaining (int): The threshold for the number of
                remaining requests before a proactive sleep is triggered.
            concurrent_requests (int): The maximum number of coroutines that
                can simultaneously access the Sentry API.
            maximum_sleep_duration (int): The maximum sleep duration in seconds
        """
        self._lock = asyncio.Lock()
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[float] = None

        self._semaphore = asyncio.Semaphore(concurrent_requests)
        self._maximum_retries = maximum_retries
        self._minimum_limit_remaining = minimum_limit_remaining
        self._retries = 0
        self._maximum_sleep_duration = maximum_sleep_duration

    async def __aenter__(self) -> "SentryRateLimiter":
        """
        Pre-request rate limit check.
        """
        self._retries = 0  # reset retries when entering the context manager
        async with self._lock:
            if (
                self._rate_limit_remaining is not None
                and self._rate_limit_reset is not None
                and self._rate_limit_remaining <= self._minimum_limit_remaining
            ):
                current_time = time.time()
                sleep_duration = self._rate_limit_reset - current_time
                if sleep_duration > 0:
                    logger.info(
                        f"Proactively sleeping for {sleep_duration:.2f} seconds "
                        f"as rate limit remaining ({self._rate_limit_remaining}) "
                        f"is at or below threshold ({self._minimum_limit_remaining})."
                    )
                    await asyncio.sleep(sleep_duration)

        await self._semaphore.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> Optional[bool]:
        """
        Handles 429 responses and backoff logic, ensuring the semaphore is always released.

        Returns:
            bool: True if the request should be retried, False otherwise
        """
        try:
            if self._is_rate_limit_error(exc_val):
                response = cast(httpx.HTTPStatusError, exc_val).response
                return await self._handle_rate_limit(response)
            return False

        finally:
            self._semaphore.release()

    @staticmethod
    def _is_rate_limit_error(exc_val: Optional[BaseException]) -> bool:
        """Check if the exception represents a rate limit error."""
        return (
            isinstance(exc_val, httpx.HTTPStatusError)
            and exc_val.response.status_code == 429
        )

    async def _handle_rate_limit(self, response: httpx.Response) -> bool:
        """
        Handle rate limit error by implementing retry logic with backoff.

        Args:
            response: The HTTP response with headers for rate limit checks.

        Returns:
            bool: True if the request should be retried, False if max retries exceeded
        """
        logger.warning(
            f"calling retry logic for 429 Too Many Requests. {self._retries}"
        )
        # Increment the retry counter for the current operation.
        # Note: self._retries is reset to 0 in `__aenter__` for each new API call.
        self._retries += 1

        # Circuit breaker: prevent infinite retries.
        # If _maximum_retries is 3, this check allows for 3 retry attempts. The 4th attempt will fail.
        if self._retries > self._maximum_retries:
            logger.error("Max retries exceeded for rate-limited request.")
            await self._update_rate_limit_state(response)
            return False

        sleep_time = self._get_sleep_retry_duration(response)
        logger.warning(f"Retrying request after {sleep_time:.2f} seconds due to 429.")
        await asyncio.sleep(sleep_time)
        return True

    async def _update_rate_limit_state(self, response: httpx.Response) -> None:
        """Updates the internal rate limit state from response headers."""
        headers = response.headers
        async with self._lock:
            remaining = headers.get("X-Sentry-Rate-Limit-Remaining")
            reset = headers.get("X-Sentry-Rate-Limit-Reset")

            if remaining is not None:
                self._rate_limit_remaining = int(remaining)
            if reset is not None:
                self._rate_limit_reset = float(reset)

            if remaining is not None and reset is not None:
                logger.debug(
                    f"Sentry rate limit state: "
                    f"Remaining={self._rate_limit_remaining}, "
                    f"ResetAt={time.ctime(self._rate_limit_reset)}"
                )

    def _get_sleep_retry_duration(self, response: httpx.Response) -> float:
        """
        Calculates the sleep duration for retries, prioritizing the 'Retry-After' header.

        It defaults to exponential backoff and overrides it with the 'Retry-After'
        header if present and valid. The final value is always capped by
        self._maximum_sleep_duration.
        """
        # 1. Default to exponential backoff as the base sleep duration.
        #    The number of retries is used for this calculation. (2^1, 2^2, ...)
        sleep_duration = 2**self._retries
        log_reason = f"exponential backoff, resulting in {sleep_duration:.2f}s"

        if retry_after_str := response.headers.get("Retry-After"):
            try:
                header_duration = float(retry_after_str)
                sleep_duration = header_duration
                log_reason = f"'Retry-After' header, resulting in {sleep_duration:.2f}s"
            except (ValueError, TypeError):
                logger.warning(
                    f"Could not parse 'Retry-After' header value: '{retry_after_str}'. "
                    f"Falling back to exponential backoff."
                )

        logger.warning(f"Rate limit wait time determined by {log_reason}.")
        return min(sleep_duration, self._maximum_sleep_duration)
