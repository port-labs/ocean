import asyncio
import time
from typing import Dict
from loguru import logger


class GitHubRateLimiter:
    """Rate limiter for GitHub API requests using a queue-based approach."""

    def __init__(self, max_requests: int = 5000, reset_time: int = 3600):
        self.max_requests = max_requests
        self.remaining_requests = max_requests
        self.reset_time = reset_time
        self.reset_at = time.time() + reset_time
        self.queue = asyncio.Queue()

        # Start a background task to reset the rate limit periodically
        asyncio.create_task(self._reset_rate_limit_periodically())

    async def acquire(self):
        """Acquire permission to make a request."""
        if self.remaining_requests <= 0:
            wait_time = self.reset_at - time.time()
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)

        # Simulate acquiring a request slot
        await self.queue.put(1)
        self.remaining_requests -= 1
        logger.debug(f"Request made. Remaining requests: {self.remaining_requests}")

    async def release(self):
        """Release a request slot."""
        await self.queue.get()
        self.queue.task_done()

    def update_rate_limit(self, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        self.remaining_requests = int(headers.get("X-RateLimit-Remaining", self.max_requests))
        self.reset_at = int(headers.get("X-RateLimit-Reset", time.time() + self.reset_time))
        logger.debug(
            f"Updated rate limit: {self.remaining_requests} requests remaining, "
            f"resets at {time.ctime(self.reset_at)}"
        )

    async def _reset_rate_limit_periodically(self):
        """Reset the rate limit periodically based on the reset time."""
        while True:
            wait_time = self.reset_at - time.time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Reset the rate limit
            self.remaining_requests = self.max_requests
            self.reset_at = time.time() + self.reset_time
            logger.info("Rate limit reset. Remaining requests restored to maximum.")

    # Add support for the asynchronous context manager protocol
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()