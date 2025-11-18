import asyncio
import time

from loguru import logger
from typing import AsyncGenerator
from contextlib import asynccontextmanager

_DEFAULT_MAX_WAIT: int = 30
_DEFAULT_BACKOFF: int = 1

AZURERM_RATELIMIT_CAPACITY = 250
AZURERM_BUCKET_REFILL_RATE = 25


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

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        max_wait: int = _DEFAULT_MAX_WAIT,
        backoff: int = _DEFAULT_BACKOFF,
    ) -> None:
        self.capacity: int = capacity
        self.refill_rate: float = refill_rate
        self.tokens: int = capacity
        self.last_refill_time: float = time.monotonic()
        self.max_wait: int = max_wait
        self._backoff: int = backoff

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

    @asynccontextmanager
    async def limit(self, tokens: int = 1) -> AsyncGenerator[None, None]:
        """Async context manager to throttle execution automatically."""
        while not self.consume(tokens):
            logger.warning(f"Rate limit hit — backing off for {self._backoff}s")
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, self.max_wait)
        try:
            yield
        finally:
            self._backoff = 1


class AdaptiveTokenBucketRateLimiter:
    """
    Adaptive Token Bucket Rate Limiter — Azure-aware & OceanClient-compatible.

    Goals:
    - Azure-intelligent: adapts refill rate based on quota headers.
    - Smooth recovery: ramps refill rate up gradually after throttling.
    - Non-intrusive: leaves retry handling to OceanAsyncClient.

    Usage:
        limiter = AdaptiveTokenBucketRateLimiter()
        async with limiter.limit():
            response = await client.get(url)
            limiter.adjust_from_headers(response.headers)

    For more details on Azure's use of this algorithm, and the default values, see:
    https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling#migrating-to-regional-throttling-and-token-bucket-algorithm
    """

    def __init__(
        self,
        capacity: int = 250,
        refill_rate: float = 25.0,
        max_wait: int = 30,
        recovery_rate: float = 1.15,
        min_refill_factor: float = 0.1,
        adjustment_cooldown: float = 1.0,
    ) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._adaptive_refill_rate = refill_rate
        self.min_refill_factor = min_refill_factor
        self.recovery_rate = recovery_rate
        self.max_wait = max_wait
        self.adjustment_cooldown = adjustment_cooldown

        self.tokens = float(capacity)
        self.last_refill_time = time.monotonic()
        self._lock = asyncio.Lock()
        self._last_adjustment_time = 0.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        added_tokens = elapsed * self._adaptive_refill_rate
        if added_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + added_tokens)
            self.last_refill_time = now

    async def _consume(self, tokens: float = 1.0) -> None:
        async with self._lock:
            while True:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                needed = tokens - self.tokens
                wait_time = needed / max(self._adaptive_refill_rate, 0.01)
                if wait_time > self.max_wait:
                    logger.error(
                        f"Rate limiter wait ({wait_time:.2f}s) exceeds max_wait threshold."
                    )
                    raise TimeoutError("Rate limiter wait exceeded max_wait.")

                logger.warning(
                    f"Waiting {wait_time:.2f}s for token refill (adaptive rate={self._adaptive_refill_rate:.2f}/s)"
                )
                await asyncio.sleep(wait_time)

    @asynccontextmanager
    async def limit(self, tokens: float = 1.0) -> AsyncGenerator[None, None]:
        """
        Context-managed async limiter:
            async with limiter.limit():
                ...
        """
        await self._consume(tokens)
        try:
            yield
        finally:
            pass  # Reserved for cooldown or future hooks

    def adjust_from_headers(self, headers: dict[str, str]) -> None:
        """
        Adjust internal refill rate based on Azure API feedback headers.
        This function is lightweight and safe to call after *every* response.
        """
        now = time.monotonic()
        if not self._should_adjust(now):
            return

        self._last_adjustment_time = now
        quota_remaining = self._parse_quota_remaining_from_headers(headers)
        if quota_remaining is not None:
            remaining_ratio = quota_remaining / float(self.capacity)
            self._log_quota_status(quota_remaining, remaining_ratio)
            self._adapt_refill_rate(remaining_ratio, quota_remaining)

    def _should_adjust(self, now: float) -> bool:
        logger.debug(
            f"Adjusting rate limiter from headers at {now}. Last adjustment at {self._last_adjustment_time} (cooldown {self.adjustment_cooldown}s)."
        )
        if now - self._last_adjustment_time < self.adjustment_cooldown:
            logger.debug(
                f"Adjustment skipped due to cooldown. Time since last adjustment: {now - self._last_adjustment_time:.2f}s"
            )
            return False
        return True

    def _parse_quota_remaining_from_headers(
        self, headers: dict[str, str]
    ) -> int | None:
        try:
            if "x-ms-ratelimit-remaining-tenant-reads" in headers:
                quota_remaining = int(headers["x-ms-ratelimit-remaining-tenant-reads"])
                logger.debug(
                    f"Found quota header: x-ms-ratelimit-remaining-tenant-reads={quota_remaining}"
                )
                return quota_remaining
            else:
                logger.debug("No x-ms-ratelimit-remaining-tenant-reads header present.")
                return None
        except Exception as e:
            logger.debug(f"Header parse error: {e}")
            return None

    def _log_quota_status(self, quota_remaining: int, remaining_ratio: float) -> None:
        logger.debug(
            f"Parsed quota_remaining: {quota_remaining}, capacity: {self.capacity}, remaining_ratio: {remaining_ratio:.3f}, current refill rate: {self._adaptive_refill_rate:.3f}/s"
        )

    def _adapt_refill_rate(self, remaining_ratio: float, quota_remaining: int) -> None:
        """
        Adjust the adaptive refill rate based on the remaining quota ratio.
        Delegates to slowdown or recovery sub-functions according to thresholds.
        """
        if remaining_ratio < 0.1:
            self._apply_slowdown(remaining_ratio, quota_remaining)
        elif remaining_ratio > 0.8 and self._adaptive_refill_rate < self.refill_rate:
            self._attempt_refill_recovery(remaining_ratio)

    def _apply_slowdown(self, remaining_ratio: float, quota_remaining: int) -> None:
        """Slow down the refill rate adaptively when quota is running out."""
        slowdown_factor = max(self.min_refill_factor, remaining_ratio)
        new_rate = self.refill_rate * slowdown_factor
        logger.debug(
            f"Nearing quota exhaustion: ratio={remaining_ratio:.3f}, applying slowdown_factor={slowdown_factor:.3f}, proposed new_rate={new_rate:.3f}/s"
        )
        if abs(new_rate - self._adaptive_refill_rate) > 0.01:
            logger.warning(
                f"Nearing quota exhaustion (remaining={quota_remaining}), "
                f"reducing refill rate → {new_rate:.2f}/s"
            )
        self._adaptive_refill_rate = new_rate

    def _attempt_refill_recovery(self, remaining_ratio: float) -> None:
        """Ramp up refill rate smoothly when quota is healthy."""
        logger.debug(
            f"Quota healthy: ratio={remaining_ratio:.3f}. Attempting refill rate recovery."
        )
        previous_rate = self._adaptive_refill_rate
        self._adaptive_refill_rate = min(
            self.refill_rate,
            self._adaptive_refill_rate * self.recovery_rate,
        )
        logger.debug(
            f"Recovered adaptive refill rate from {previous_rate:.3f}/s to {self._adaptive_refill_rate:.3f}/s"
        )
        logger.info(
            f"Recovering refill rate → {self._adaptive_refill_rate:.2f}/s (quota healthy)"
        )
