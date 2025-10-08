import asyncio
import time

from loguru import logger


class RateLimitHandler:
    @staticmethod
    async def handle_rate_limit(success: bool, wait_time: int = 1) -> None:
        if not success:
            logger.info("Rate limit exceeded, waiting for 1 second")
            await asyncio.sleep(wait_time)


class TokenBucketRateLimiter:
    """
    Implements a token bucket algorithm for rate limiting.

    This class is used to manage API request throttling based on a token bucket
    algorithm. The bucket has a certain capacity of tokens, and it refills at a
    constant rate. Each request consumes one or more tokens. If the bucket is
    empty, requests are denied until new tokens are added.

    For more details on Azure's use of this algorithm, see:
    https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling#migrating-to-regional-throttling-and-token-bucket-algorithm
    """
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
