from typing import Callable, Awaitable, Any, Optional
from dataclasses import dataclass
import math
import asyncio
from .logging import Logger, LoggerProtocol


class RateLimitError(Exception):
    def __init__(self, retry_after: Optional[float] = None):
        super().__init__("Rate limit retries exhausted")
        self.retry_after = retry_after


class TransientError(Exception):
    """A generic transient error that may be retried."""

    pass


@dataclass
class RateLimiterConfig:
    requests_per_window: int
    window_seconds: int


class AsyncRateLimiter:
    """
    An asynchronous rate limiter using the token bucket algorithm.

    Ref: https://en.wikipedia.org/wiki/Token_bucket
    """

    def __init__(self, config: RateLimiterConfig):
        self.config = config
        self.allowance = config.requests_per_window
        self.last_check = asyncio.get_event_loop().time()

    async def acquire(self):
        current = asyncio.get_event_loop().time()
        time_passed = current - self.last_check
        self.last_check = current
        self.allowance += time_passed * (
            self.config.requests_per_window / self.config.window_seconds
        )
        if self.allowance > self.config.requests_per_window:
            self.allowance = self.config.requests_per_window

        if self.allowance < 1.0:
            retry_after = (1.0 - self.allowance) * (
                self.config.window_seconds / self.config.requests_per_window
            )
            raise RateLimitError(retry_after=retry_after)
        else:
            self.allowance -= 1.0


RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_BASE_DELAY = 1.0  # in seconds
MAX_BACKOFF_WAIT = 60.0  # in seconds

_rate_limiter_config = RateLimiterConfig(requests_per_window=100, window_seconds=10)
SAILPOINT_LIMITER = AsyncRateLimiter(_rate_limiter_config)


async def exponential_backoff_retry(
    func: Callable[..., Awaitable[Any]],
    *args,
    max_attempts: int = RATE_LIMIT_MAX_ATTEMPTS,
    base_delay: float = RATE_LIMIT_BASE_DELAY,
    logger: LoggerProtocol,
    **kwargs,
) -> Any:
    """
    - Respects `Retry-After` if present in response
    - Otherwise, retries with exponential backoff
    """
    delay = base_delay
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_attempts - 1:
                logger.log_error(
                    message="Max retry attempts exceeded",
                    error=e,
                    context=f"attempt: {attempt + 1} of {max_attempts}",
                )
                break
            delay = e.retry_after or base_delay * math.pow(2, attempt)
            logger.log_retry_decision(
                attempt=attempt + 1,
                max_attempts=max_attempts,
                backoff_ms=int(delay * 1000),
                reason="RateLimitError",
            )
            await asyncio.sleep(min(delay, MAX_BACKOFF_WAIT))
        except TransientError:
            delay = base_delay * math.pow(2, attempt)

            logger.log_retry_decision(
                attempt=attempt + 1,
                max_attempts=max_attempts,
                backoff_ms=int(delay * 1000),
                reason="TransientError",
            )
            await asyncio.sleep(min(delay, MAX_BACKOFF_WAIT))

    raise RuntimeError("Max retry attempts exceeded")
