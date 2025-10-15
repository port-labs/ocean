import asyncio
import random
import time
from datetime import datetime
from functools import partial
from http import HTTPStatus
from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    Mapping,
    Union,
    cast,
    Optional,
    List,
)
import httpx
from dateutil.parser import isoparse
import logging

MAX_BACKOFF_WAIT_IN_SECONDS = 60
_ON_RETRY_CALLBACK: Callable[[httpx.Request], httpx.Request] | None = None
_RETRY_CONFIG_CALLBACK: Callable[[], "RetryConfig"] | None = None


def register_on_retry_callback(
    _on_retry_callback: Callable[[httpx.Request], httpx.Request]
) -> None:
    global _ON_RETRY_CALLBACK
    _ON_RETRY_CALLBACK = _on_retry_callback


def register_retry_config_callback(
    retry_config_callback: Callable[[], "RetryConfig"]
) -> None:
    """Register a callback function that returns a RetryConfig instance.

    The callback will be called when a RetryTransport needs to be created.

    Args:
        retry_config_callback: A function that returns a RetryConfig instance
    """
    global _RETRY_CONFIG_CALLBACK
    _RETRY_CONFIG_CALLBACK = retry_config_callback


class RetryConfig:
    """Configuration class for retry behavior that can be customized per integration."""

    def __init__(
        self,
        max_attempts: int = 10,
        max_backoff_wait: float = MAX_BACKOFF_WAIT_IN_SECONDS,
        base_delay: float = 0.1,
        jitter_ratio: float = 0.1,
        respect_retry_after_header: bool = True,
        retryable_methods: Optional[Iterable[str]] = None,
        retry_status_codes: Optional[Iterable[int]] = None,
        retry_after_headers: Optional[List[str]] = None,
        additional_retry_status_codes: Optional[Iterable[int]] = None,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            max_backoff_wait: Maximum backoff wait time in seconds
            base_delay: Base delay for exponential backoff
            jitter_ratio: Jitter ratio for backoff (0-0.5)
            respect_retry_after_header: Whether to respect Retry-After header
            retryable_methods: HTTP methods that can be retried (overrides defaults if provided)
            retry_status_codes: DEPRECATED - use additional_retry_status_codes instead
            retry_after_headers: Custom headers to check for retry timing (e.g., ['X-RateLimit-Reset', 'Retry-After'])
            additional_retry_status_codes: Additional status codes to retry (extends system defaults)
        """
        self.max_attempts = max_attempts
        self.max_backoff_wait = max_backoff_wait
        self.base_delay = base_delay
        self.jitter_ratio = jitter_ratio
        self.respect_retry_after_header = respect_retry_after_header

        # Default retryable methods - always include these unless explicitly overridden
        default_methods = frozenset(
            ["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        self.retryable_methods = (
            frozenset(retryable_methods) if retryable_methods else default_methods
        )

        # Default retry status codes - always include these for system reliability
        default_status_codes = frozenset(
            [
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.BAD_REQUEST,
            ]
        )

        # Additional status codes to retry (extends defaults)
        additional_codes = (
            frozenset(additional_retry_status_codes)
            if additional_retry_status_codes
            else frozenset()
        )

        # Combine defaults with additional codes for extensibility
        self.retry_status_codes = default_status_codes | additional_codes
        self.retry_after_headers = retry_after_headers or ["Retry-After"]

        if jitter_ratio < 0 or jitter_ratio > 0.5:
            raise ValueError(
                f"Jitter ratio should be between 0 and 0.5, actual {jitter_ratio}"
            )


# Adapted from https://github.com/encode/httpx/issues/108#issuecomment-1434439481
class RetryTransport(httpx.AsyncBaseTransport, httpx.BaseTransport):
    """
    A custom HTTP transport that automatically retries requests using an exponential backoff strategy
    for specific HTTP status codes and request methods.

    Args:
        wrapped_transport (Union[httpx.BaseTransport, httpx.AsyncBaseTransport]): The underlying HTTP transport
            to wrap and use for making requests.
        max_attempts (int, optional): The maximum number of times to retry a request before giving up. Defaults to 10.
        max_backoff_wait (float, optional): The maximum time to wait between retries in seconds. Defaults to 60.
        backoff_factor (float, optional): The factor by which the wait time increases with each retry attempt.
            Defaults to 0.1.
        jitter_ratio (float, optional): The amount of jitter to add to the backoff time. Jitter is a random
            value added to the backoff time to avoid a "thundering herd" effect. The value should be between 0 and 0.5.
            Defaults to 0.1.
        respect_retry_after_header (bool, optional): Whether to respect the Retry-After header in HTTP responses
            when deciding how long to wait before retrying. Defaults to True.
        retryable_methods (Iterable[str], optional): The HTTP methods that can be retried. Defaults to
            ["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"].
        retry_status_codes (Iterable[int], optional): The HTTP status codes that can be retried. Defaults to
            [429, 502, 503, 504].
        retry_config (RetryConfig, optional): Configuration for retry behavior. If not provided, uses defaults.
        logger (Any, optional): The logger to use for logging retries.

    Attributes:
        _wrapped_transport (Union[httpx.BaseTransport, httpx.AsyncBaseTransport]): The underlying HTTP transport
            being wrapped.
        _retry_config (RetryConfig): The retry configuration object.
        _logger (Any): The logger to use for logging retries.
    """

    def __init__(
        self,
        wrapped_transport: Union[httpx.BaseTransport, httpx.AsyncBaseTransport],
        max_attempts: int = 10,
        max_backoff_wait: float = MAX_BACKOFF_WAIT_IN_SECONDS,
        base_delay: float = 0.1,
        jitter_ratio: float = 0.1,
        respect_retry_after_header: bool = True,
        retryable_methods: Iterable[str] | None = None,
        retry_status_codes: Iterable[int] | None = None,
        retry_config: Optional[RetryConfig] = None,
        logger: Any | None = None,
    ) -> None:
        """
        Initializes the instance of RetryTransport class with the given parameters.

        Args:
            wrapped_transport (Union[httpx.BaseTransport, httpx.AsyncBaseTransport]):
                The transport layer that will be wrapped and retried upon failure.
            max_attempts (int, optional):
                The maximum number of times the request can be retried in case of failure.
                Defaults to 10.
            max_backoff_wait (float, optional):
                The maximum amount of time (in seconds) to wait before retrying a request.
                Defaults to 60.
            base_delay (float, optional):
                The factor by which the waiting time will be multiplied in each retry attempt.
                Defaults to 0.1.
            jitter_ratio (float, optional):
                The ratio of randomness added to the waiting time to prevent simultaneous retries.
                Should be between 0 and 0.5. Defaults to 0.1.
            respect_retry_after_header (bool, optional):
                A flag to indicate if the Retry-After header should be respected.
                If True, the waiting time specified in Retry-After header is used for the waiting time.
                Defaults to True.
            retryable_methods (Iterable[str], optional):
                The HTTP methods that can be retried. Defaults to ['HEAD', 'GET', 'PUT', 'DELETE', 'OPTIONS', 'TRACE'].
            retry_status_codes (Iterable[int], optional):
                The HTTP status codes that can be retried.
                Defaults to [429, 502, 503, 504].
            retry_config (RetryConfig, optional):
                Configuration for retry behavior. If not provided, uses default configuration.
            logger (Any): The logger to use for logging retries.
        """
        self._wrapped_transport = wrapped_transport

        if retry_config is not None:
            self._retry_config = retry_config
        elif _RETRY_CONFIG_CALLBACK is not None:
            self._retry_config = _RETRY_CONFIG_CALLBACK()
        else:
            self._retry_config = RetryConfig(
                max_attempts=max_attempts,
                max_backoff_wait=max_backoff_wait,
                base_delay=base_delay,
                jitter_ratio=jitter_ratio,
                respect_retry_after_header=respect_retry_after_header,
                retryable_methods=retryable_methods,
                retry_status_codes=retry_status_codes,
            )

        self._logger = logger

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """
        Sends an HTTP request, possibly with retries.

        Args:
            request (httpx.Request): The request to send.

        Returns:
            httpx.Response: The response received.

        """
        try:
            transport: httpx.BaseTransport = self._wrapped_transport  # type: ignore
            if self._is_retryable_method(request):
                send_method = partial(transport.handle_request)
                response = self._retry_operation(request, send_method)
            else:
                response = transport.handle_request(request)

            self._log_response_size(request, response)

            return response
        except Exception as e:
            if not self._is_retryable_method(request) and self._logger is not None:
                self._logger.exception(f"{repr(e)} - {request.url}", exc_info=e)
            raise e

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Sends an HTTP request, possibly with retries.

        Args:
            request: The request to perform.

        Returns:
            The response.

        """
        try:
            transport: httpx.AsyncBaseTransport = self._wrapped_transport  # type: ignore
            if self._is_retryable_method(request):
                send_method = partial(transport.handle_async_request)
                response = await self._retry_operation_async(request, send_method)
            else:
                response = await transport.handle_async_request(request)

            await self._log_response_size_async(request, response)

            return response
        except Exception as e:
            # Retyable methods are logged via _log_error
            if not self._is_retryable_method(request) and self._logger is not None:
                self._logger.exception(f"{repr(e)} - {request.url}", exc_info=e)
            raise e

    async def aclose(self) -> None:
        """
        Closes the underlying HTTP transport, terminating all outstanding connections and rejecting any further
        requests.

        This should be called before the object is dereferenced, to ensure that connections are properly cleaned up.
        """
        transport: httpx.AsyncBaseTransport = self._wrapped_transport  # type: ignore
        await transport.aclose()

    def close(self) -> None:
        """
        Closes the underlying HTTP transport, terminating all outstanding connections and rejecting any further
        requests.

        This should be called before the object is dereferenced, to ensure that connections are properly cleaned up.
        """
        transport: httpx.BaseTransport = self._wrapped_transport  # type: ignore
        transport.close()

    def _is_retryable_method(self, request: httpx.Request) -> bool:
        return (
            request.method in self._retry_config.retryable_methods
            or request.extensions.get("retryable", False)
        )

    def _should_retry(self, response: httpx.Response) -> bool:
        return response.status_code in self._retry_config.retry_status_codes

    def _log_error(
        self,
        request: httpx.Request,
        error: Exception | None,
    ) -> None:
        if not self._logger:
            return

        if isinstance(error, httpx.ConnectTimeout):
            self._logger.error(
                f"Request {request.method} {request.url} failed to connect: {str(error)}"
            )
        elif isinstance(error, httpx.TimeoutException):
            self._logger.error(
                f"Request {request.method} {request.url} failed with a timeout exception: {str(error)}"
            )
        elif isinstance(error, httpx.HTTPError):
            self._logger.error(
                f"Request {request.method} {request.url} failed with an HTTP error: {str(error)}"
            )

    def _log_before_retry(
        self,
        request: httpx.Request,
        sleep_time: float,
        response: httpx.Response | None,
        error: Exception | None,
    ) -> None:
        if self._logger and response:
            self._logger.warning(
                f"Request {request.method} {request.url} failed with status code:"
                f" {response.status_code}, retrying in {sleep_time} seconds."  # noqa: F821
            )
        elif self._logger and error:
            self._logger.warning(
                f"Request {request.method} {request.url} failed with exception:"
                f" {type(error).__name__} - {str(error) or 'No error message'}, retrying in {sleep_time} seconds."
            )

    def _should_log_response_size(self, request: httpx.Request) -> bool:
        return self._logger is not None and not request.url.host.endswith("getport.io")

    def _get_content_length(self, response: httpx.Response) -> int | None:
        content_length = response.headers.get("Content-Length") or response.headers.get(
            "content-length"
        )
        if content_length:
            return int(content_length)
        return None

    async def _log_response_size_async(
        self, request: httpx.Request, response: httpx.Response
    ) -> None:
        """Log the size of the response."""
        if not self._should_log_response_size(request):
            return

        # Try to get content length from headers first
        content_length = self._get_content_length(response)
        if content_length is not None:
            size_info = content_length
        else:
            # If no Content-Length header, try to get actual content size
            try:
                actual_size = len(await response.aread())
                size_info = actual_size
            except Exception as e:
                cast(logging.Logger, self._logger).error(
                    f"Error getting response size: {e}"
                )
                return

        cast(logging.Logger, self._logger).info(
            f"Response for {request.method} {request.url} - Size: {size_info} bytes"
        )

    def _log_response_size(
        self, request: httpx.Request, response: httpx.Response
    ) -> None:
        if not self._should_log_response_size(request):
            return

        content_length = self._get_content_length(response)
        if content_length is not None:
            size_info = content_length
        else:
            # If no Content-Length header, try to get actual content size
            try:
                actual_size = len(response.read())
                size_info = actual_size
            except Exception as e:
                cast(logging.Logger, self._logger).error(
                    f"Error getting response size: {e}"
                )
                return

        cast(logging.Logger, self._logger).info(
            f"Response for {request.method} {request.url} - Size: {size_info} bytes"
        )

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        return response.status_code in self._retry_config.retry_status_codes

    def _calculate_sleep(
        self, attempts_made: int, headers: Union[httpx.Headers, Mapping[str, str]]
    ) -> float:
        # Check custom retry headers first, then fall back to Retry-After
        if self._retry_config.respect_retry_after_header:
            for header_name in self._retry_config.retry_after_headers:
                if header_value := (headers.get(header_name) or "").strip():
                    sleep_time = self._parse_retry_header(header_value)
                    if sleep_time is not None:
                        return min(sleep_time, self._retry_config.max_backoff_wait)

        # Fall back to exponential backoff
        backoff = self._retry_config.base_delay * (2 ** (attempts_made - 1))
        jitter = (backoff * self._retry_config.jitter_ratio) * random.choice([1, -1])
        total_backoff = backoff + jitter
        return min(total_backoff, self._retry_config.max_backoff_wait)

    def _parse_retry_header(self, header_value: str) -> Optional[float]:
        """Parse retry header value and return sleep time in seconds.

        Args:
            header_value: The header value to parse (e.g., "30", "2023-12-01T12:00:00Z")

        Returns:
            Sleep time in seconds if parsing succeeds, None if the header value cannot be parsed
        """
        if header_value.isdigit():
            return float(header_value)

        try:
            # Try to parse as ISO date (common for rate limit headers like X-RateLimit-Reset)
            parsed_date = isoparse(header_value).astimezone()
            diff = (parsed_date - datetime.now().astimezone()).total_seconds()
            if diff > 0:
                return diff
        except ValueError:
            pass

        return None

    async def _retry_operation_async(
        self,
        request: httpx.Request,
        send_method: Callable[..., Coroutine[Any, Any, httpx.Response]],
    ) -> httpx.Response:
        remaining_attempts = self._retry_config.max_attempts
        attempts_made = 0
        response: httpx.Response | None = None
        error: Exception | None = None
        while True:
            if attempts_made > 0:
                sleep_time = self._calculate_sleep(attempts_made, {})
                self._log_before_retry(request, sleep_time, response, error)
                await asyncio.sleep(sleep_time)

            error = None
            response = None
            try:
                response = await send_method(request)
                response.request = request
                if remaining_attempts < 1 or not (
                    await self._should_retry_async(response)
                ):
                    return response
                await response.aclose()
            except httpx.ConnectTimeout as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.ReadTimeout as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.TimeoutException as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.HTTPError as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            if _ON_RETRY_CALLBACK:
                request = _ON_RETRY_CALLBACK(request)
            attempts_made += 1
            remaining_attempts -= 1

    def _retry_operation(
        self,
        request: httpx.Request,
        send_method: Callable[..., httpx.Response],
    ) -> httpx.Response:
        remaining_attempts = self._retry_config.max_attempts
        attempts_made = 0
        response: httpx.Response | None = None
        error: Exception | None = None

        while True:
            if attempts_made > 0:
                sleep_time = self._calculate_sleep(attempts_made, {})
                self._log_before_retry(request, sleep_time, response, error)
                time.sleep(sleep_time)

            error = None
            response = None
            try:
                response = send_method(request)
                response.request = request
                if remaining_attempts < 1 or not self._should_retry(response):
                    return response
                response.close()
            except httpx.ConnectTimeout as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.TimeoutException as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.HTTPError as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            if _ON_RETRY_CALLBACK:
                request = _ON_RETRY_CALLBACK(request)
            attempts_made += 1
            remaining_attempts -= 1
