import asyncio
import time
from typing import Optional, Any

import httpx
from loguru import logger

MAXIMUM_CONCURRENT_REQUESTS_DEFAULT = 1
MAXIMUM_LIMIT_ON_RETRIES = 3
MINIMUM_LIMIT_REMAINING = 5


class SentryRateLimiter:
    """
    A client wrapper that handles Sentry API rate limits gracefully.

    This class inspects Sentry's rate-limiting headers on each response
    and introduces delays to prevent hitting the rate limit. It handles both
    proactive (based on X-Sentry-Rate-Limit-Remaining) and reactive
    (based on 429 Too Many Requests with a Retry-After header) rate limiting.

    Sentry Rate Limit Headers:
    - X-Sentry-Rate-Limit-Limit: The total number of requests allowed in the window.
    - X-Sentry-Rate-Limit-Remaining: The number of requests remaining in the window.
    - X-Sentry-Rate-Limit-Reset: The UTC epoch timestamp when the window resets.

    For more information, see: https://docs.sentry.io/api/ratelimits/
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
    ):
        """
        Initializes the SentryRateLimiter.

        Args:
            client (httpx.AsyncClient): The client used for making API calls.
        """

        self.client = client

        # Rate limit state, protected by a lock for thread safety
        self._lock = asyncio.Lock()
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[float] = None

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

    async def request(
        self, url: str, method: str = "GET", params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """
        Makes a rate-limited request to the Sentry API.

        This is the core method that wraps the actual HTTP call, applying
        rate-limiting logic before and after the request.

        Args:
            method (str): The HTTP method to use for the request.
            params (dict[str, Any] | None): Optional query parameters to include in the request.
            url (str): The URL for the request.

        Returns:
            httpx.Response: The response object from the successful request.

        Raises:
            httpx.HTTPStatusError: If the request fails after all retries.
        """
        retries = 0
        while True:
            try:
                await self._wait_if_needed()
                response = await self.client.request(method, url, params=params)
                await self._update_rate_limit_state(response)

                if response.status_code == 429:
                    retries += 1
                    if retries > MAXIMUM_LIMIT_ON_RETRIES:
                        logger.error("Max retries exceeded for rate-limited request.")
                        response.raise_for_status()  # Raise the final httpx.HTTPStatusError

                    sleep_time = self._get_sleep_retry_duration(response, retries)
                    await asyncio.sleep(sleep_time)
                    continue  # Retry the request

                # For any other non-2xx status, raise an exception immediately
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Got HTTP error to url: {url} with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
