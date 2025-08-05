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
        """
        self._lock = asyncio.Lock()
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[float] = None

        self._semaphore = asyncio.Semaphore(concurrent_requests)
        self._maximum_retries = maximum_retries
        self._minimum_limit_remaining = minimum_limit_remaining

        # We will store the last response here to handle 429 in __aexit__
        self._last_response: Optional[httpx.Response] = None
        self._retries = 0

    async def __aenter__(self) -> "SentryRateLimiter":
        """
        Pre-request rate limit check.
        """
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
        Handles 429 responses and backoff logic.
        """
        try:
            if self._last_response and self._last_response.status_code == 429:
                self._retries += 1
                if self._retries > self._maximum_retries:
                    logger.error("Max retries exceeded for rate-limited request.")
                    self._last_response.raise_for_status()

                sleep_time = self._get_sleep_retry_duration(
                    self._last_response, self._retries
                )
                logger.info(
                    f"Retrying request after {sleep_time:.2f} seconds due to 429."
                )
                self._semaphore.release()
                await asyncio.sleep(sleep_time)
                return True

            if self._last_response:
                await self._update_rate_limit_state(self._last_response)

            if exc_type and exc_type is not httpx.HTTPStatusError:
                self._semaphore.release()
                return False

        except Exception as e:
            logger.error(f"Error in aexit: {e}")
            self._semaphore.release()
            return False

        self._semaphore.release()
        return False

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

    @staticmethod
    def _get_sleep_retry_duration(response: httpx.Response, retry_count: int) -> float:
        """
        Calculates the sleep duration for 429 Too Many Requests retries.
        """
        retry_after_str = response.headers.get("Retry-After")
        if retry_after_str:
            try:
                sleep_duration = float(retry_after_str)
                logger.warning(
                    f"Received 429 Too Many Requests. "
                    f"Retrying after {sleep_duration:.2f}s (attempt {retry_count})."
                )
                return sleep_duration
            except (ValueError, TypeError):
                pass

        sleep_duration = 2**retry_count
        logger.warning(
            f"Received 429 status without a valid 'Retry-After' header. "
            f"Using exponential backoff. Sleeping for {sleep_duration:.2f}s."
        )
        return sleep_duration
