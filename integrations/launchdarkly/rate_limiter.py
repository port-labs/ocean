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
        max_retries: int = 3,
        minimum_limit_remaining: int = 1,
        maximum_sleep_duration: int = 60,
    ) -> None:
        """
        Initializes the rate limiter.

        Args:
            max_concurrent: Max number of concurrent in-flight requests.
            max_retries: Max number of retries for a rate-limited request.
            minimum_limit_remaining: Proactively sleep if remaining requests fall
                below this number.
            maximum_sleep_duration: The maximum time in seconds to sleep during a
                reactive backoff.
        """
        self.max_retries = max_retries
        self._minimum_limit_remaining = minimum_limit_remaining
        self._maximum_sleep_duration = maximum_sleep_duration

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()
        self._retries: int = 0

        self._limit: Optional[int] = None
        self._remaining: Optional[int] = None
        self._reset_time: Optional[float] = None

    @property
    def seconds_until_reset(self) -> float:
        """Calculates the time in seconds until the rate limit window resets."""
        if self._reset_time:
            return self._reset_time - time.time()
        return 0.0

    async def __aenter__(self) -> "LaunchDarklyRateLimiter":
        """Acquires semaphore and proactively sleeps if the rate limit is low."""
        await self._semaphore.acquire()
        self._retries = 0

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
        Handles 429 responses and backoff logic, ensuring the semaphore is
        always released. Returns True to signal the client to retry the request.
        """
        try:
            if (
                isinstance(exc_val, httpx.HTTPStatusError)
                and exc_val.response.status_code == 429
            ):
                response = exc_val.response
                logger.warning(f"Rate limit hit. Handling response: {response.headers}")
                return await self._handle_rate_limit_error(response)
            return False
        finally:
            self._semaphore.release()

    async def _update_rate_limits(self, headers: httpx.Headers) -> None:
        """
        Updates the internal rate limit status from response headers. This should
        be called by the client on every successful response to keep the limiter's
        state accurate.
        """
        async with self._lock:
            try:
                limit = headers.get("X-Ratelimit-Route-Limit")
                remaining = headers.get("X-Ratelimit-Route-Remaining")
                reset_ms = headers.get("X-Ratelimit-Reset")

                if limit and remaining and reset_ms:
                    logger.info(
                        f"Updating rate limit status: {remaining} / {limit} and resets in {reset_ms}"
                    )
                    self._limit = int(limit)
                    self._remaining = int(remaining)
                    self._reset_time = float(reset_ms) / 1000.0
                    self._log_rate_limit_status()

            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse LaunchDarkly rate limit headers: {e}")

    async def _handle_rate_limit_error(self, response: httpx.Response) -> bool:
        """
        Handles a 429 error by sleeping and determining if a retry is warranted.
        """
        self._retries += 1
        await self._update_rate_limits(response.headers)

        if self._retries > self.max_retries:
            logger.error(
                f"Max retries ({self.max_retries}) exceeded for rate-limited request."
            )
            return False

        sleep_duration = self.seconds_until_reset + 0.5
        final_sleep = min(sleep_duration, self._maximum_sleep_duration)

        logger.warning(
            f"Rate limit hit. Retrying request in {final_sleep:.2f} seconds "
            f"(attempt {self._retries}/{self.max_retries})."
        )
        await asyncio.sleep(final_sleep)
        return True

    def _log_rate_limit_status(self) -> None:
        """Logs the current rate limit status if available."""
        if self._remaining and self._limit:
            logger.warning(
                f"LaunchDarkly Rate Limit: {self._remaining} remaining. "
                f"Limit: {self._limit}. "
                f"Resets in {self.seconds_until_reset:.2f}s."
            )
