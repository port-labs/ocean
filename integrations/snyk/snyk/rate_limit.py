import asyncio
from enum import StrEnum
from typing import Any, Optional, AsyncGenerator

import httpx
from httpx import Timeout
from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client
import time


class RateLimiter:
    def __init__(self, concurrency_limit: int, requests_per_minute: int):
        self.semaphore = asyncio.BoundedSemaphore(concurrency_limit)
        self.requests_per_minute = requests_per_minute
        self.request_count = 0
        self.reset_time = time.monotonic() + 60
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            current_time = time.monotonic()
            if current_time >= self.reset_time:
                self.request_count = 0
                self.reset_time = current_time + 60
            if self.request_count >= self.requests_per_minute:
                sleep_time = self.reset_time - current_time
                logger.info(
                    f"Rate limit reached, sleeping for {sleep_time:.2f} seconds"
                )
                await asyncio.sleep(sleep_time)
                self.request_count = 0
                self.reset_time = time.monotonic() + 60
            self.request_count += 1
        await self.semaphore.acquire()

    def release(self):
        self.semaphore.release()
