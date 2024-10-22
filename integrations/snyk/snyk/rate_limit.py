import asyncio
from loguru import logger
import time


class RateLimiter:
    def __init__(self, concurrency_limit: int, requests_per_minute: int) -> None:
        self.semaphore: asyncio.BoundedSemaphore = asyncio.BoundedSemaphore(concurrency_limit)
        self.requests_per_minute: int = requests_per_minute
        self.request_count: int = 0
        self.reset_time: float = time.monotonic() + 60
        self.lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            current_time: float = time.monotonic()
            if current_time >= self.reset_time:
                self.request_count = 0
                self.reset_time = current_time + 60
            if self.request_count >= self.requests_per_minute:
                sleep_time: float = self.reset_time - current_time
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
                self.request_count = 0
                self.reset_time = time.monotonic() + 60
            self.request_count += 1
        await self.semaphore.acquire()

    def release(self) -> None:
        self.semaphore.release()
