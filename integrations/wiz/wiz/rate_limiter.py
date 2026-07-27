import asyncio
import time


class TokenBucketRateLimiter:
    """Async token-bucket limiter for pacing API requests."""

    def __init__(self, rate: int) -> None:
        self._rate = rate
        self._tokens = float(rate)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    float(self._rate), self._tokens + elapsed * self._rate
                )
                self._last_refill = now

                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                wait_time = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
