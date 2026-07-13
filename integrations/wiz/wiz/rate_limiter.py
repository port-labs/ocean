import asyncio
import time


class TokenBucketRateLimiter:
    """Async token-bucket limiter for pacing API requests."""

    def __init__(self, rate: float, *, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")

        self._rate = rate
        self._burst = burst if burst is not None else max(1, int(rate))
        self._tokens = float(self._burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def rate(self) -> float:
        return self._rate

    def set_rate(self, rate: float, *, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")

        self._rate = rate
        if burst is not None:
            self._burst = burst
        else:
            self._burst = max(1, int(rate))
        self._tokens = min(self._tokens, float(self._burst))

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    float(self._burst), self._tokens + elapsed * self._rate
                )
                self._last_refill = now

                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                wait_time = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
