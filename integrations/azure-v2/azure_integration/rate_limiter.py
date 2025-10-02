import time


class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_rate: float) -> None:
        self.capacity: int = capacity
        self.refill_rate: float = refill_rate
        self.tokens: int = capacity
        self.last_refill_time: float = time.time()

    def consume(self, tokens: int) -> bool:
        self.refill()
        if self.tokens < tokens:
            return False
        self.tokens -= tokens
        return True

    def refill(self) -> None:
        current_time = time.time()
        self.tokens = int(
            min(
                self.capacity,
                self.tokens + (current_time - self.last_refill_time) * self.refill_rate,
            )
        )
        self.last_refill_time = current_time
