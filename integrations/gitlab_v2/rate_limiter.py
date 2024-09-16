import asyncio
import time
from loguru import logger
from httpx import Response, HTTPStatusError
from datetime import datetime, timezone
from httpx import AsyncClient, Timeout

# class GitLabRateLimiter:
#     def __init__(self, max_requests: int = 2000, time_window: int = 60):
#         self.max_requests = max_requests
#         self.time_window = time_window
#         self.request_timestamps = []
#         self.lock = asyncio.Lock()
#
#     async def acquire(self):
#         """Wait if the rate limit is exceeded."""
#         async with self.lock:
#             now = time.time()
#             # Clean up old timestamps outside the time window
#             self.request_timestamps = [ts for ts in self.request_timestamps if now - ts <= self.time_window]
#             if len(self.request_timestamps) >= self.max_requests:
#                 # Calculate sleep time until the rate limit resets
#                 sleep_time = self.request_timestamps[0] + self.time_window - now
#                 if sleep_time > 0:
#                     logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
#                     await asyncio.sleep(sleep_time)
#             self.request_timestamps.append(now)
#
#     def update_limits(self, headers: Dict[str, str]):
#         """Update the rate limit based on response headers."""
#         self.max_requests = int(headers.get('RateLimit-Limit', self.max_requests))
#         reset_time = int(headers.get('RateLimit-Reset', 0))
#         if reset_time:
#             self.time_window = max(reset_time - int(time.time()), 1)
#
#     @property
#     def requests_remaining(self):
#         """Returns the number of remaining requests before hitting the rate limit."""
#         now = time.time()
#         return self.max_requests - len([ts for ts in self.request_timestamps if now - ts <= self.time_window])

class GitLabRateLimiter:
    def __init__(self, max_requests: int = 7200, time_window: int = 3600):
        """RateLimiter manages rate limiting based on request timestamps and headers."""
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_timestamps = []
        self.lock = asyncio.Lock()

    async def wait_for_slot(self):
        """Wait until a request slot becomes available."""
        async with self.lock:
            now = time.time()
            self._clean_old_requests(now)

            if len(self.request_timestamps) >= self.max_requests:
                sleep_time = self.request_timestamps[0] + self.time_window - now
                if sleep_time > 0:
                    logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                    await asyncio.sleep(sleep_time)

    def _clean_old_requests(self, now: float):
        """Remove request timestamps that fall outside the time window."""
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts <= self.time_window]

    def update_limits(self, headers: dict[str, str]):
        """Update the rate limits based on response headers."""
        self.max_requests = int(headers.get('RateLimit-Limit', self.max_requests))
        reset_time = int(headers.get('RateLimit-Reset', 0))

        if reset_time:
            reset_interval = reset_time - int(time.time())
            self.time_window = max(reset_interval, 1)
            logger.info(f"Rate limit updated: {self.max_requests} requests per {self.time_window} seconds.")

    @property
    def requests_remaining(self):
        """Calculate the remaining requests in the current time window."""
        now = time.time()
        self._clean_old_requests(now)
        return self.max_requests - len(self.request_timestamps)

