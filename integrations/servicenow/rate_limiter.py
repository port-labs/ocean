import asyncio
import time
from typing import Optional

import httpx
from loguru import logger

LIMIT_HEADER = "x-ratelimit-limit"
LIMIT_RESET_HEADER = "x-ratelimit-reset"
RETRY_AFTER_HEADER = "retry-after"


class ServiceNowRateLimiter:
    """Rate limiter for ServiceNow Table API requests.

    Tracks rate limit state from response headers and proactively paces
    requests to avoid hitting 429 errors. ServiceNow sends these headers
    when a rate limit rule is configured:

    On 200 and 429 responses:
        - X-RateLimit-Limit: max requests per hour
        - X-RateLimit-Reset: Unix timestamp when the limit window resets

    On 429 responses only:
        - Retry-After: seconds to wait before retrying

    ServiceNow does NOT send X-RateLimit-Remaining,
    so we track request count internally and reset when the window expires.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        self._limit: Optional[int] = None
        self._reset_time: Optional[float] = None
        self._request_count: int = 0

    @property
    def seconds_until_reset(self) -> float:
        if self._reset_time is not None:
            return max(0.0, self._reset_time - time.time())
        return 0.0

    async def __aenter__(self) -> "ServiceNowRateLimiter":
        async with self._lock:
            if self._reset_time is not None and time.time() >= self._reset_time:
                self._request_count = 0
                self._reset_time = None

            if (
                self._limit is not None
                and self._request_count >= self._limit
                and self._reset_time is not None
            ):
                wait_time = self.seconds_until_reset
                if wait_time > 0:
                    logger.info(
                        f"Rate limit: {self._request_count}/{self._limit} requests used, "
                        f"waiting {wait_time:.1f}s until window resets"
                    )
                    await asyncio.sleep(wait_time)
                self._request_count = 0
                self._reset_time = None

            self._request_count += 1

        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def update_from_headers(self, headers: httpx.Headers) -> None:
        async with self._lock:
            try:
                limit_header = headers.get(LIMIT_HEADER)
                reset_header = headers.get(LIMIT_RESET_HEADER)
                retry_after = headers.get(RETRY_AFTER_HEADER)

                if reset_header:
                    reset_time = float(reset_header)
                    if reset_time <= max(time.time(), self._reset_time or 0.0):
                        return
                    self._reset_time = reset_time
                    if limit_header:
                        self._limit = int(limit_header)
                    logger.debug(
                        f"Rate limit status - {self._request_count}/{self._limit} requests, "
                        f"resets in {self.seconds_until_reset:.1f}s"
                    )

                if retry_after:
                    wait_seconds = int(retry_after)
                    retry_after_reset = time.time() + wait_seconds
                    if self._reset_time is None:
                        self._reset_time = retry_after_reset
                    else:
                        self._reset_time = max(self._reset_time, retry_after_reset)
                    logger.info(
                        f"Rate limit 429 received: Retry-After {wait_seconds}s, "
                        f"limit {self._limit} req/hr"
                    )

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse ServiceNow rate limit headers: {e}")
