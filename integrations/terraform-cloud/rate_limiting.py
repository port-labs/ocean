from dataclasses import dataclass
import time
import asyncio


@dataclass
class TokenBucket:
    capacity: int  # Maximum tokens
    rate: float  # Tokens per second
    tokens: float  # Current tokens
    last_update: float  # Last token update timestamp

    @classmethod
    def create(cls, rate: int, capacity: int) -> "TokenBucket":
        return cls(
            capacity=capacity, rate=rate, tokens=capacity, last_update=time.time()
        )

    def _refill(self) -> None:
        now = time.time()
        delta = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + delta * self.rate)
        self.last_update = now

    async def acquire(self) -> None:
        while True:
            self._refill()
            if self.tokens >= 1:
                self.tokens -= 1
                return
            # Wait for token refill
            await asyncio.sleep(1 / self.rate)
