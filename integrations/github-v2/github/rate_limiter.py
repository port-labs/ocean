import asyncio
import time
from typing import Mapping, Optional, Type
from loguru import logger


MAX_CONCURRENT_REQUESTS = 10


class GithubRateLimiter:
    """Rate limiter for GitHub API requests."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.rate_limit = {
            "remaining": 5000,
            "reset": time.time() + 3600,
        }

    async def __aenter__(self) -> "GithubRateLimiter":
        await self._semaphore.acquire()
        if self.rate_limit["remaining"] <= 1:
            wait_time = self.rate_limit["reset"] - time.time()
            if wait_time > 0:
                logger.warning(
                    f"Rate limit reached. Waiting {wait_time:.2f} seconds..."
                )
                await asyncio.sleep(wait_time)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self._semaphore.release()

    def update_rate_limit(self, headers: Mapping[str, str]) -> None:
        """Update rate limit information from response headers."""
        self.rate_limit = {
            "remaining": int(headers.get("X-RateLimit-Remaining", 5000)),
            "reset": int(headers.get("X-RateLimit-Reset", time.time() + 3600)),
        }
        logger.debug(
            f"Updated rate limit: {self.rate_limit['remaining']} requests remaining, "
            f"resets at {time.ctime(self.rate_limit['reset'])}"
        )
