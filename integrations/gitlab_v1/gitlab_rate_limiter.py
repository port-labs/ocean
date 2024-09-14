import asyncio
import time
from typing import Dict
from loguru import logger


class GitLabRateLimiter:
    def __init__(self, max_requests: int = 2000, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_timestamps = []
        self.lock = asyncio.Lock()


    async def acquire(self):
        async with self.lock:
            now = time.time()
            self.request_timestamps = [ts for ts in self.request_timestamps if now - ts <= self.time_window]

            if len(self.request_timestamps) >= self.max_requests:
                sleep_time = self.request_timestamps[0] + self.time_window - now
                if sleep_time > 0:
                    logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                    await asyncio.sleep(sleep_time)

            self.request_timestamps.append(now)


    def update_limits(self, headers: Dict[str, str]):
        self.max_requests = int(headers.get('RateLimit-Limit', self.max_requests))
        reset_time = int(headers.get('RateLimit-Reset', 0))
        if reset_time:
            self.time_window = max(reset_time - int(time.time()), 1)


    @property
    def requests_remaining(self):
        now = time.time()
        return self.max_requests - len([ts for ts in self.request_timestamps if now - ts <= self.time_window])
