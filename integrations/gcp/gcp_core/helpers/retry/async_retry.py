import asyncio
import time
import functools
from typing import Any, Callable, Iterable

from loguru import logger
from google.api_core.exceptions import (
    TooManyRequests,
    ServiceUnavailable,
    DeadlineExceeded,
    InternalServerError,
)
from google.auth import exceptions as auth_exceptions
import requests.exceptions

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from google.api_core.retry_async import exponential_sleep_generator
from google.api_core.retry.retry_base import (
    RetryFailureReason,
    build_retry_error,
    _BaseRetry,
    _retry_error_helper,
    if_exception_type,
)


_DEFAULT_INITIAL_DELAY_BETWEEN_RETRIES: float = 5.0
_DEFAULT_MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS: float = 60.0
_DEFAULT_MULTIPLIER_FOR_EXPONENTIAL_BACKOFF: float = 2.0
_DEFAULT_TIMEOUT: float = 360.0


if_transient_error = if_exception_type(
    TooManyRequests,
    ServiceUnavailable,
    DeadlineExceeded,
    InternalServerError,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    auth_exceptions.TransportError,
)


def log_retry_attempt(error: Exception) -> None:
    """Log a warning when a retryable error occurs."""
    logger.warning(f"Retrying due to {error.__class__.__name__} error")


if_transient_error = if_exception_type(
    TooManyRequests,
    ServiceUnavailable,
    DeadlineExceeded,
    InternalServerError,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    auth_exceptions.TransportError,
)


async def retry_generator_target(
    target: Callable[..., ASYNC_GENERATOR_RESYNC_TYPE],
    predicate: Callable[[Exception], bool],
    sleep_generator: Iterable[float],
    timeout: float | None = None,
    on_error: Callable[..., None] | None = None,
    exception_factory: Callable[
        [list[Exception], RetryFailureReason, float | None],
        tuple[Exception, Exception | None],
    ] = build_retry_error,
    *args: Any,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Retry an async generator function if it fails.

    Args:
        target (Callable[[], AsyncGenerator]): The async generator function to call and retry. This must be a
            nullary function - apply arguments with `functools.partial`
        predicate (Callable[Exception]): A callable used to determine if an exception raised by the target should be considered retryable.
        sleep_generator (Iterable[float]): An infinite iterator that determines how long to sleep between retries.
        timeout (Optional[float]): How long to keep retrying the generator, in seconds.
        on_error (Optional[Callable[Exception]]): If given, the on_error callback will be called with each retryable exception raised by the target.
        exception_factory: A function that is called when the retryable reaches a terminal failure state, used to construct an exception to be raised.
        *args, **kwargs: Arguments to pass to the generator function.

    Yields:
        ASYNC_GENERATOR_RESYNC_TYPE: Items yielded by the generator function.

    Raises:
        ValueError: If the sleep generator stops yielding values.
        Exception: a custom exception specified by the exception_factory if provided.
            If no exception_factory is provided:
                google.api_core.RetryError: If the timeout is exceeded while retrying.
                Exception: If the target raises an error that isn't retryable.
    """

    timeout = kwargs.get("deadline", timeout)
    deadline = time.monotonic() + timeout if timeout is not None else None
    error_list: list[Exception] = []

    for sleep in sleep_generator:
        try:
            async for item in target():
                yield item
            return
        except Exception as exc:
            _retry_error_helper(
                exc,
                deadline,
                sleep,
                error_list,
                predicate,
                on_error,
                exception_factory,
                timeout,
            )
            # if exception not raised, sleep before next attempt
            await asyncio.sleep(sleep)

    raise ValueError("Sleep generator stopped yielding sleep values.")


class AsyncGeneratorRetry(_BaseRetry):
    """An Exponential Backoff Retry Decorator for Async Generators in Google's AsyncRetry Framework.

    This class is a decorator used to add exponential back-off retry behavior
    to an async generator.

    Args:
        predicate (Callable[Exception]): A callable that should return ``True``
            if the given exception is retryable.
        initial (float): The minimum amount of time to delay in seconds. This
            must be greater than 0.
        maximum (float): The maximum amount of time to delay in seconds.
        multiplier (float): The multiplier applied to the delay.
        timeout (Optional[float]): How long to keep retrying in seconds.
            Note: timeout is only checked before initiating a retry, so the target may
            run past the timeout value as long as it is healthy.
        on_error (Optional[Callable[Exception]]): A function to call while processing
            a retryable exception. Any error raised by this function will
            *not* be caught.
        # deadline (float): DEPRECATED use ``timeout`` instead. If set it will
        # override ``timeout`` parameter.
    """

    def __call__(
        self,
        func: Callable[..., ASYNC_GENERATOR_RESYNC_TYPE],
    ) -> Callable[..., ASYNC_GENERATOR_RESYNC_TYPE]:
        """Wrap an async generator with retry behavior.

        Args:
            func (Callable): The async generator function to add retry behavior to.

        Returns:
            Callable: A callable that will invoke the async generator with retry behavior.
        """

        @functools.wraps(func)
        async def retry_wrapped_generator(
            *args: Any, **kwargs: Any
        ) -> ASYNC_GENERATOR_RESYNC_TYPE:
            sleep_generator = exponential_sleep_generator(
                self._initial, self._maximum, multiplier=self._multiplier
            )

            async for response in retry_generator_target(
                functools.partial(func, *args, **kwargs),
                predicate=self._predicate,
                sleep_generator=sleep_generator,
                timeout=self._timeout,
                on_error=self._on_error,
            ):
                yield response

        return retry_wrapped_generator


async_generator_retry: AsyncGeneratorRetry = AsyncGeneratorRetry(
    initial=_DEFAULT_INITIAL_DELAY_BETWEEN_RETRIES,
    predicate=if_transient_error,
    maximum=_DEFAULT_MAXIMUM_DELAY_BETWEEN_RETRY_ATTEMPTS,
    multiplier=_DEFAULT_MULTIPLIER_FOR_EXPONENTIAL_BACKOFF,
    timeout=_DEFAULT_TIMEOUT,
    on_error=log_retry_attempt,
)
