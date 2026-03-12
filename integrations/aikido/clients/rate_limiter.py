"""
Aikido Rate Limiter

Proactive rate limiting to stay under Aikido's API limits:
- Standard: 20 requests/minute per workspace
- Target: ≤15 requests/minute (4 second minimum between requests)

This prevents 429 errors and the resulting extended sync times.
"""

import asyncio
import time
from loguru import logger

DEFAULT_MIN_REQUEST_INTERVAL = 4.0


class AikidoRateLimiter:
    """
    Time-based rate limiter for Aikido API requests.

    Ensures a minimum interval between requests to stay under
    Aikido's rate limit of 20 requests/minute.
    """

    def __init__(self, min_interval: float = DEFAULT_MIN_REQUEST_INTERVAL):
        """
        Initialize the rate limiter.

        Args:
            min_interval: Minimum seconds between requests (default: 4.0)
        """
        self.min_interval = min_interval
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Waits if necessary to maintain the minimum interval between requests.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time

            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(
                    f"Rate limiter: waiting {wait_time:.2f}s before next request"
                )
                await asyncio.sleep(wait_time)

            self._last_request_time = time.monotonic()

    async def __aenter__(self) -> "AikidoRateLimiter":
        """Context manager entry - acquires rate limit slot."""
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        pass
