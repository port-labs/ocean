import asyncio
import random
import time
from typing import (
    Any,
    Callable,
    Type,
    Tuple,
    Coroutine,
)
from loguru import logger
from google.api_core.exceptions import TooManyRequests, ServiceUnavailable
from aiolimiter import AsyncLimiter
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

# Constants for retry logic
_DEFAULT_RETRIABLE_ERROR_TYPES = (TooManyRequests, ServiceUnavailable)
_DEFAULT_INITIAL_DELAY_BETWEEN_RETRIES: float = 5.0
_DEFAULT_MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS: float = 60.0
_DEFAULT_MULTIPLIER_FOR_EXPONENTIAL_BACKOFF: float = 2.0
_DEFAULT_TIMEOUT: float = 300.0

# Constants for rate limiting
_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0
_DEFAULT_RATE_LIMIT_QUOTA: int = int(ocean.integration_config[
    "search_all_resources_per_minute_quota"
])


class AsyncRateLimiter:
    def __init__(
        self,
        max_rate: int = _DEFAULT_RATE_LIMIT_QUOTA,
        time_period: float = _DEFAULT_RATE_LIMIT_TIME_PERIOD,
    ):
        self.limiter = AsyncLimiter(max_rate=max_rate, time_period=time_period)
        logger.info(
            f"Initialized rate limiter with {max_rate} requests per {time_period} seconds."
        )

    async def paginate_with_limit(
        self,
        func: Callable[..., ASYNC_GENERATOR_RESYNC_TYPE],
        *args: Any,
        **kwargs: Any,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async with self.limiter:
            async for item in func(*args, **kwargs):
                yield item

    async def execute_with_limit(
        self,
        func: Callable[..., Coroutine[Any, Any, RAW_ITEM]],
        *args: Any,
        **kwargs: Any,
    ) -> RAW_ITEM:
        async with self.limiter:
            return await func(*args, **kwargs)


class AsyncRetry:
    def __init__(
        self,
        exception_to_check: Tuple[
            Type[Exception], ...
        ] = _DEFAULT_RETRIABLE_ERROR_TYPES,
        timeout: float = _DEFAULT_TIMEOUT,
        delay: float = _DEFAULT_INITIAL_DELAY_BETWEEN_RETRIES,
        max_delay: float = _DEFAULT_MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS,
        backoff: float = _DEFAULT_MULTIPLIER_FOR_EXPONENTIAL_BACKOFF,
        jitter: bool = True,
    ):
        self.exception_to_check = exception_to_check
        self.timeout = timeout
        self.delay = delay
        self.max_delay = max_delay
        self.backoff = backoff
        self.jitter = jitter

    def _get_delay(self, attempt: int) -> float:
        """Calculate the delay for the current attempt."""
        delay = self.delay * (self.backoff ** (attempt - 1))
        minimum_delay = min(delay, self.max_delay)
        if self.jitter:
            minimum_delay += random.uniform(0, delay)
        return minimum_delay

    def retry_paginated_resource(
        self, func: Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]
    ) -> Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]:
        async def wrapper(*args: Any, **kwargs: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
            start_time = time.monotonic()
            attempt = 0
            while True:
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                    return
                except self.exception_to_check as e:
                    attempt += 1
                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time >= self.timeout:
                        logger.warning(
                            f"Timeout reached. Giving up after {elapsed_time:.2f} seconds."
                        )
                        raise e
                    next_delay = self._get_delay(attempt)

                    if elapsed_time + next_delay >= self.timeout:
                        logger.warning(
                            "Making final retry attempt due to timeout constraints."
                        )
                        async for item in func(*args, **kwargs):
                            yield item
                        return

                    logger.warning(
                        f"Retrying due to {e.__class__.__name__} error in {next_delay:.2f} seconds..."
                    )
                    await asyncio.sleep(next_delay)

        return wrapper

    def retry_single_resource(
        self, func: Callable[..., Coroutine[Any, Any, RAW_ITEM]]
    ) -> Callable[..., Coroutine[Any, Any, RAW_ITEM]]:
        async def wrapper(*args: Any, **kwargs: Any) -> RAW_ITEM:
            start_time = time.monotonic()
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except self.exception_to_check as e:
                    attempt += 1
                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time >= self.timeout:
                        logger.warning(
                            f"Timeout reached. Giving up after {elapsed_time:.2f} seconds."
                        )
                        raise e
                    next_delay = self._get_delay(attempt)

                    # Check if next delay would exceed the timeout, making this the final attempt
                    if elapsed_time + next_delay >= self.timeout:
                        logger.warning(
                            f"Making final attempt for {func.__name__} due to timeout constraints."
                        )
                        return await func(*args, **kwargs)

                    logger.warning(
                        f"Retrying {func.__name__} due to {e.__class__.__name__} error in {next_delay:.2f} seconds..."
                    )
                    await asyncio.sleep(next_delay)

        return wrapper


rate_limiter = AsyncRateLimiter()
async_retry = AsyncRetry()
