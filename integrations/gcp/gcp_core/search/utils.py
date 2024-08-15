import asyncio
from typing import Any, Callable, AsyncGenerator
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from google.api_core.retry_async import AsyncRetry
from google.api_core.exceptions import (
    TooManyRequests,
    ServiceUnavailable,
)


RETRIABLE_ERROR_TYPES = (TooManyRequests, ServiceUnavailable)
INITIAL_DELAY_BEFORE_FIRST_RETRY_ATTEMPT = 1.0
MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS = 60.0
MULTIPLIER_FOR_EXPONENTIAL_BACKOFF = 2.0
TOTAL_TIME_ALLOWED_FOR_RETRIES = 300.0

MAX_CONCURRENT_CALLS = 10
semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_CALLS)


def is_retryable(error: Exception) -> bool:
    """Check if the error is retryable based on defined error types."""
    return isinstance(error, RETRIABLE_ERROR_TYPES)


def log_retry_attempt(error: Exception) -> None:
    """Log a warning when a retryable error occurs."""
    logger.warning(f"Retrying due to {error.__class__.__name__} error: {error}")


retry_policy = AsyncRetry(
    predicate=is_retryable,
    on_error=log_retry_attempt,
    initial=INITIAL_DELAY_BEFORE_FIRST_RETRY_ATTEMPT,
    maximum=MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS,
    multiplier=MULTIPLIER_FOR_EXPONENTIAL_BACKOFF,
    deadline=TOTAL_TIME_ALLOWED_FOR_RETRIES,
    timeout=TOTAL_TIME_ALLOWED_FOR_RETRIES,
)


async def execute_with_concurrency_control(
    callable_func: Callable[..., AsyncGenerator[Any, None]], *args: Any, **kwargs: Any
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Execute a callable with concurrency control using a bounded semaphore."""
    async with semaphore:
        async for item in callable_func(*args, **kwargs):
            yield item
