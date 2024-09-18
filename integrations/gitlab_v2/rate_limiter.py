import asyncio
import time

from loguru import logger

class GitLabRateLimiter:
    def __init__(self, max_requests: int = 7200, time_window: int = 3600):
        """RateLimiter manages rate limiting using BoundedSemaphore."""
        self.max_requests = max_requests
        self.time_window = time_window
        self.semaphore = asyncio.BoundedSemaphore(max_requests)
        asyncio.create_task(self._reset_semaphore())

    async def wait_for_slot(self):
        """Wait until a request slot becomes available."""
        await self.semaphore.acquire()
        logger.info(f"Request allowed. Remaining requests: {self.semaphore._value}")

    async def _reset_semaphore(self):
        """Reset the semaphore periodically to allow new requests."""
        while True:
            await asyncio.sleep(self.time_window)
            self.semaphore = asyncio.BoundedSemaphore(self.max_requests)
            logger.info(f"Rate limit reset: {self.max_requests} requests allowed in the next window.")

    def update_limits(self, headers: dict[str, str]):
        """Update the rate limits dynamically based on response headers."""
        self.max_requests = int(headers.get('RateLimit-Limit', self.max_requests))
        reset_time = int(headers.get('RateLimit-Reset', 0))

        if reset_time:
            reset_interval = reset_time - int(time.time())
            self.time_window = max(reset_interval, 1)
            logger.info(f"Rate limits updated: {self.max_requests} requests per {self.time_window} seconds.")
            self.semaphore = asyncio.BoundedSemaphore(self.max_requests)
