import asyncio
import time
from typing import Optional, Any, Type
from datetime import datetime
import httpx
from loguru import logger

MAX_CONCURRENT_REQUESTS = 10
MINIMUM_LIMIT_REMAINING = 1


class JiraRateLimiter:
    """
    Asynchronous rate limiter for Atlassian Jira Cloud APIs.

    Conforms to Ocean's async standards by supporting concurrent control,
    proactive throttling, and reactive backoff using Jira rate limit headers.
    """

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS,
        minimum_limit_remaining: int = MINIMUM_LIMIT_REMAINING,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        self._limit: Optional[int] = None
        self._remaining: Optional[int] = None
        self._near_limit: bool = False
        self._reset_time: Optional[float] = None
        self._retry_after: Optional[float] = None

        self._minimum_limit_remaining = minimum_limit_remaining

    def _get_header_key(self, headers: httpx.Headers, header_type: str) -> str:
        """
        Factory method to get the appropriate header key based on type and availability.
        Prefers standard headers over beta-prefixed ones.
        """
        match header_type:
            case "limit":
                return (
                    "x-ratelimit-limit"
                    if "x-ratelimit-limit" in headers
                    else "x-beta-ratelimit-limit"
                )
            case "remaining":
                return (
                    "x-ratelimit-remaining"
                    if "x-ratelimit-remaining" in headers
                    else "x-beta-ratelimit-remaining"
                )
            case "near_limit":
                return (
                    "x-ratelimit-nearlimit"
                    if "x-ratelimit-nearlimit" in headers
                    else "x-beta-ratelimit-nearlimit"
                )
            case "reset":
                return (
                    "x-ratelimit-reset"
                    if "x-ratelimit-reset" in headers
                    else "x-beta-ratelimit-reset"
                )
            case "retry_after":
                return "retry-after" if "retry-after" in headers else "beta-retry-after"
            case "reason":
                return (
                    "ratelimit-reason"
                    if "ratelimit-reason" in headers
                    else "x-beta-ratelimit-reason"
                )
            case _:
                raise ValueError(f"Unknown header type: {header_type}")

    @property
    def seconds_until_reset(self) -> float:
        """Time in seconds until the current rate limit window resets."""
        if self._reset_time:
            return max(0.0, self._reset_time - time.time())
        logger.debug("Rate limit reset time is not set")
        return 0.0

    async def update_rate_limit_headers(self, headers: httpx.Headers) -> None:
        """
        Updates the internal rate limit status from response headers. This should
        be called by the client after every request, including failed ones.

        Handles both standard and beta-prefixed headers, preferring standard.
        On 429, sets remaining to 0 and prioritizes Retry-After for reset calculation.
        """
        async with self._lock:
            try:
                limit_key = self._get_header_key(headers, "limit")
                remaining_key = self._get_header_key(headers, "remaining")
                near_limit_key = self._get_header_key(headers, "near_limit")
                reset_key = self._get_header_key(headers, "reset")
                retry_after_key = self._get_header_key(headers, "retry_after")

                self._limit = int(headers.get(limit_key))
                self._remaining = int(headers.get(remaining_key))
                self._near_limit = headers.get(near_limit_key) == "true"
                self._retry_after = float(headers.get(retry_after_key, 0.0))

                reset_time_str = headers.get(reset_key)
                if reset_time_str:
                    dt = datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
                    self._reset_time = dt.timestamp()

                reason_key = self._get_header_key(headers, "reason")
                if headers.get(reason_key):
                    logger.warning(
                        f"Rate limit breached for this reason: {headers.get(reason_key)}"
                    )
            except Exception as e:
                logger.error(f"Failed to update rate limit headers: {e}")

    async def __aenter__(self) -> "JiraRateLimiter":
        """Acquires semaphore and proactively sleeps if the rate limit is low."""
        await self._semaphore.acquire()

        async with self._lock:
            near_limit_condition = self._near_limit
            percentage_condition = (
                self._limit is not None
                and self._remaining is not None
                and self._remaining <= self._minimum_limit_remaining
            )
            if near_limit_condition or percentage_condition:
                sleep_duration = self.seconds_until_reset
                if sleep_duration > 0:
                    logger.debug(
                        f"Proactively sleeping for {sleep_duration:.2f}s as rate limit "
                        f"is near threshold (near_limit={self._near_limit}, "
                        f"remaining={self._remaining}, limit={self._limit})."
                    )
                    await asyncio.sleep(sleep_duration)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Always release the semaphore after the request completes."""
        self._semaphore.release()
