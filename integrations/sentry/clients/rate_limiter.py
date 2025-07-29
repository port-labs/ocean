import asyncio
import time
from typing import Optional, Callable, Awaitable, Type, Any

import httpx
from loguru import logger

MINIMUM_LIMIT_REMAINING = 10
MAXIMUM_LIMIT_ON_RETRIES = 3


class SentryRateLimiter:
    """
    Orchestrates Sentry API requests to handle rate limits gracefully.

    This class provides a method to execute a request function, wrapping it
    in rate-limiting logic. It inspects Sentry's rate-limiting headers on each
    response and introduces delays to prevent hitting the rate limit. It handles
    both proactive (based on X-Sentry-Rate-Limit-Remaining) and reactive
    (based on 429 Too Many Requests with a Retry-After header) rate limiting.

    Sentry Rate Limit Headers:
    - X-Sentry-Rate-Limit-Limit: The total number of requests allowed in the window.
    - X-Sentry-Rate-Limit-Remaining: The number of requests remaining in the window.
    - X-Sentry-Rate-Limit-Reset: The UTC epoch timestamp when the window resets.

    For more information, see: https://docs.sentry.io/api/ratelimits/

    Usage:
        limiter = SentryRateLimiter()
        client = httpx.AsyncClient()
        request_func = lambda: client.get("https://sentry.io/api/...")
        response = await limiter.execute(request_func)
    """

    def __init__(self) -> None:
        """
        Initializes the SentryRateLimiter.
        """
        # Rate limit state, protected by a lock for thread safety
        self._lock = asyncio.Lock()
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[float] = None

    async def __aenter__(self) -> "SentryRateLimiter":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> Optional[bool]:
        # No-op or post-request cleanup
        return None

    async def _update_rate_limit_state(self, response: httpx.Response) -> None:
        """Updates the internal rate limit state from response headers."""
        headers = response.headers
        async with self._lock:
            # Persist the last known values if headers are absent in a response
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

    async def _wait_if_needed(self) -> None:
        """Checks the current rate limit state and sleeps if necessary."""
        sleep_duration = None

        async with self._lock:
            # If we have no rate limit info yet, proceed with the request
            if self._rate_limit_remaining is None or self._rate_limit_reset is None:
                return

            # Proactive sleep if we are close to the limit
            if self._rate_limit_remaining <= MINIMUM_LIMIT_REMAINING:
                current_time = time.time()
                # Only sleep if the reset time is in the future
                if self._rate_limit_reset > current_time:
                    sleep_duration = self._rate_limit_reset - current_time

        if sleep_duration:
            logger.info(
                f"Rate limit threshold reached ({self._rate_limit_remaining} remaining). "
                f"Sleeping for {sleep_duration:.2f} seconds."
            )
            await asyncio.sleep(sleep_duration)

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
                    f"Retrying after {sleep_duration:.2f}s (attempt {retry_count}/{MAXIMUM_LIMIT_ON_RETRIES})."
                )
                return sleep_duration
            except (ValueError, TypeError):
                pass

        # Fallback to exponential backoff if Retry-After is missing/invalid
        sleep_duration = 2**retry_count
        logger.warning(
            f"Received 429 status without a valid 'Retry-After' header. "
            f"Using exponential backoff. Sleeping for {sleep_duration:.2f}s."
        )
        return sleep_duration

    async def execute(
        self, request_func: Callable[[], Awaitable[httpx.Response]]
    ) -> httpx.Response:
        """
        Executes a request function with rate-limiting logic.

        This is the core method that wraps the actual HTTP call, applying
        rate-limiting logic before and after the request.

        Args:
            request_func (Callable[[], Awaitable[httpx.Response]]): An async function
                that takes no arguments and returns an awaitable httpx.Response. This function
                is responsible for making the actual HTTP request.

        Returns:
            httpx.Response: The response object from the successful request.

        Raises:
            httpx.HTTPStatusError: If the request fails after all retries.
        """
        retries = 0
        while True:
            try:
                await self._wait_if_needed()
                response = await request_func()
                await self._update_rate_limit_state(response)

                request = response.request
                logger.debug(
                    f"Received response with status code: {response.status_code} for {request.method} {request.url}"
                )

                if response.status_code == 429:
                    retries += 1
                    if retries > MAXIMUM_LIMIT_ON_RETRIES:
                        logger.error("Max retries exceeded for rate-limited request.")
                        response.raise_for_status()  # Raise the final httpx.HTTPStatusError

                    sleep_time = self._get_sleep_retry_duration(response, retries)
                    logger.info(
                        f"Retrying request for {request.method} {request.url} after {sleep_time:.2f} seconds due to 429."
                    )
                    await asyncio.sleep(sleep_time)
                    continue  # Retry the request

                # For any other non-2xx status, raise an exception immediately
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                req = e.request
                logger.error(
                    f"Got HTTP error to url: {req.url} with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                req = e.request
                logger.error(
                    f"HTTP error occurred while requesting {req.method} {req.url}: {e}"
                )
                raise
