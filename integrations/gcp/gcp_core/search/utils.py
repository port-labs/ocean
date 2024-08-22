import asyncio
import random
import time
import functools
from typing import (
    Any,
    Callable,
    Type,
    Tuple,
    Coroutine,
)
from loguru import logger
from google.api_core.exceptions import (
    TooManyRequests,
    ServiceUnavailable,
    DeadlineExceeded,
    InternalServerError,
)
from google.auth import exceptions as auth_exceptions
import requests.exceptions

from aiolimiter import AsyncLimiter
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from google.api_core.retry_async import AsyncRetry

# Constants for retry logic
_DEFAULT_RETRIABLE_ERROR_TYPES = (
    TooManyRequests,
    ServiceUnavailable,
    DeadlineExceeded,
    InternalServerError,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    auth_exceptions.TransportError,
)
_DEFAULT_INITIAL_DELAY_BETWEEN_RETRIES: float = 5.0
_DEFAULT_MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS: float = 60.0
_DEFAULT_MULTIPLIER_FOR_EXPONENTIAL_BACKOFF: float = 2.0
_DEFAULT_TIMEOUT: float = 300.0

# Constants for rate limiting
_DEFAULT_RATE_LIMIT_TIME_PERIOD: float = 60.0
_DEFAULT_RATE_LIMIT_QUOTA: int = int(
    ocean.integration_config["search_all_resources_per_minute_quota"]
)


def _exponential_sleep_generator(initial, maximum, multiplier):
    max_delay = min(initial, maximum)
    while True:
        yield random.uniform(0.0, max_delay)
        max_delay = min(max_delay * multiplier, maximum)


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
        predicate: Tuple[Type[Exception], ...] = _DEFAULT_RETRIABLE_ERROR_TYPES,
        timeout: float = _DEFAULT_TIMEOUT,
        initial: float = _DEFAULT_INITIAL_DELAY_BETWEEN_RETRIES,
        maximum: float = _DEFAULT_MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS,
        multiplier: float = _DEFAULT_MULTIPLIER_FOR_EXPONENTIAL_BACKOFF,
        jitter: bool = True,
    ):
        self.predicate = predicate
        self.timeout = timeout
        self.initial = initial
        self.maximum = maximum
        self.multiplier = multiplier
        self.jitter = jitter

    def retry_paginated_resource(
        self, func: Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]
    ) -> Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]:

        @functools.wraps(func)
        async def retry_wrapped_function(
            *args: Any, **kwargs: Any
        ) -> ASYNC_GENERATOR_RESYNC_TYPE:
            start_time = time.monotonic()
            sleep_generator = _exponential_sleep_generator(
                self.initial, self.maximum, self.multiplier
            )
            for sleep in sleep_generator:
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                    return
                except self.predicate as exc:
                    elapsed_time = time.monotonic() - start_time

                    if elapsed_time + sleep > self.timeout:
                        logger.error(
                            f"Timeout reached. Giving up due to {exc.__class__.__name__} error after {elapsed_time:.2f} seconds."
                        )
                        raise exc

                    logger.warning(
                        f"Retrying due to {exc.__class__.__name__} error in {sleep:.2f} seconds..."
                    )
                    await asyncio.sleep(sleep)
                except Exception as e:
                    logger.error(
                        f"Failed to execute function '{func.__name__}' with arguments {args} and keyword arguments {kwargs}. Error: {e}"
                    )
                    return

            raise ValueError("Sleep generator stopped yielding sleep values.")

        return retry_wrapped_function

    def retry_single_resource(
        self, func: Callable[..., Coroutine[Any, Any, RAW_ITEM]]
    ) -> Callable[..., Coroutine[Any, Any, RAW_ITEM]]:

        @functools.wraps(func)
        async def retry_wrapped_function(*args: Any, **kwargs: Any) -> RAW_ITEM:
            start_time = time.monotonic()
            sleep_generator = _exponential_sleep_generator(
                self.initial, self.maximum, self.multiplier
            )
            for sleep in sleep_generator:
                try:
                    return await func(*args, **kwargs)
                except self.predicate as exc:
                    elapsed_time = time.monotonic() - start_time

                    if elapsed_time + sleep > self.timeout:
                        logger.error(
                            f"Timeout reached. Giving up due to {exc.__class__.__name__} error after {elapsed_time:.2f} seconds."
                        )
                        raise exc

                    logger.warning(
                        f"Retrying due to {exc.__class__.__name__} error in {sleep:.2f} seconds..."
                    )
                    await asyncio.sleep(sleep)
                except Exception as e:
                    logger.error(
                        f"Failed to execute function '{func.__name__}' with arguments {args} and keyword arguments {kwargs}. Error: {e}"
                    )
                    return
            raise ValueError("Sleep generator stopped yielding sleep values.")

        return retry_wrapped_function


rate_limiter = AsyncRateLimiter()
async_retry = AsyncRetry()
