import asyncio
import functools
import random
from datetime import datetime
from http import HTTPStatus
from typing import Any, Callable, Coroutine, Iterable, Mapping

import aiohttp
from aiohttp import ClientResponse
from dateutil.parser import isoparse
from loguru import logger


# Adapted from https://github.com/encode/httpx/issues/108#issuecomment-1434439481n
class RetryRequestClass(aiohttp.ClientRequest):
    RETRYABLE_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"])
    RETRYABLE_STATUS_CODES = frozenset(
        [
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        ]
    )
    MAX_BACKOFF_WAIT = 60

    def __init__(
            self,
            method,
            url,
            max_attempts: int = 10,
            max_backoff_wait: float = MAX_BACKOFF_WAIT,
            backoff_factor: float = 0.1,
            jitter_ratio: float = 0.1,
            respect_retry_after_header: bool = True,
            retryable_methods: Iterable[str] | None = None,
            retry_status_codes: Iterable[int] | None = None,
            *args,
            **kwargs
    ) -> None:
        """
        Initializes the instance of RetryTransport class with the given parameters.

        Args:
            max_attempts (int, optional):
                The maximum number of times the request can be retried in case of failure.
                Defaults to 10.
            max_backoff_wait (float, optional):
                The maximum amount of time (in seconds) to wait before retrying a request.
                Defaults to 60.
            backoff_factor (float, optional):
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
            logger (Any): The logger to use for logging retries.
        """
        if jitter_ratio < 0 or jitter_ratio > 0.5:
            raise ValueError(
                f"Jitter ratio should be between 0 and 0.5, actual {jitter_ratio}"
            )

        self._max_attempts = max_attempts
        self._backoff_factor = backoff_factor
        self._respect_retry_after_header = respect_retry_after_header
        self._retryable_methods = (
            frozenset(retryable_methods)
            if retryable_methods
            else self.RETRYABLE_METHODS
        )
        self._retry_status_codes = (
            frozenset(retry_status_codes)
            if retry_status_codes
            else self.RETRYABLE_STATUS_CODES
        )
        self._jitter_ratio = jitter_ratio
        self._max_backoff_wait = max_backoff_wait

        super().__init__(method, url, *args, **kwargs)

    def _is_retryable(self) -> bool:
        return self.method in self._retryable_methods

    def _log_error(
            self,
            error: Exception | None,
    ) -> None:
        if isinstance(error, aiohttp.ServerConnectionError):
            logger.error(
                f"Request {self.method} {self.url} failed to connect: {str(error)}"
            )
        elif isinstance(error, aiohttp.ConnectionTimeoutError):
            logger.error(
                f"Request {self.method} {self.url} failed with a timeout exception: {str(error)}"
            )
        elif isinstance(error, aiohttp.ClientError):
            logger.error(
                f"Request {self.method} {self.url} failed with an HTTP error: {str(error)}"
            )

    async def _should_retry_async(self, response: ClientResponse) -> bool:
        return response.status in self._retry_status_codes

    def _calculate_sleep(
            self, attempts_made: int, headers: Mapping[str, str]
    ) -> float:
        # Retry-After
        # The Retry-After response HTTP header indicates how long the user agent should wait before
        # making a follow-up request. There are three main cases this header is used:
        # - When sent with a 503 (Service Unavailable) response, this indicates how long the service
        #   is expected to be unavailable.
        # - When sent with a 429 (Too Many Requests) response, this indicates how long to wait before
        #   making a new request.
        # - When sent with a redirect response, such as 301 (Moved Permanently), this indicates the
        #   minimum time that the user agent is asked to wait before issuing the redirected request.
        retry_after_header = (headers.get("Retry-After") or "").strip()
        if self._respect_retry_after_header and retry_after_header:
            if retry_after_header.isdigit():
                return float(retry_after_header)

            try:
                parsed_date = isoparse(
                    retry_after_header
                ).astimezone()  # converts to local time
                diff = (parsed_date - datetime.now().astimezone()).total_seconds()
                if diff > 0:
                    return min(diff, self._max_backoff_wait)
            except ValueError:
                pass

        backoff = self._backoff_factor * (2 ** (attempts_made - 1))
        jitter = (backoff * self._jitter_ratio) * random.choice([1, -1])
        total_backoff = backoff + jitter
        return min(total_backoff, self._max_backoff_wait)

    def _log_before_retry(
            self,
            sleep_time: float,
            response: ClientResponse | None,
            error: Exception | None,
    ) -> None:
        if response:
            logger.warning(
                f"Request {self.method} {self.url} failed with status code:"
                f" {response.status}, retrying in {sleep_time} seconds."  # noqa: F821
            )
        elif error:
            logger.warning(
                f"Request {self.method} {self.url} failed with exception:"
                f" {type(error).__name__} - {str(error) or 'No error message'}, retrying in {sleep_time} seconds."
            )

    async def _retry_operation_async(
            self, request: Callable[..., Coroutine[Any, Any, ClientResponse]]
    ) -> ClientResponse:
        remaining_attempts = self._max_attempts
        attempts_made = 0
        response: ClientResponse | None = None
        error: Exception | None = None
        while True:
            if attempts_made > 0:
                sleep_time = self._calculate_sleep(attempts_made, response.headers if response else {})
                self._log_before_retry(sleep_time, response, error)
                await asyncio.sleep(sleep_time)

            error = None
            response = None
            try:
                response = await request()
                if remaining_attempts < 1 or not (
                        await self._should_retry_async(response)
                ):
                    return response
            except (aiohttp.ServerConnectionError, aiohttp.ConnectionTimeoutError, aiohttp.ClientError) as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(error)
                    raise
            attempts_made += 1
            remaining_attempts -= 1

    async def send(self, conn: "Connection") -> "ClientResponse":
        request = functools.partial(
            super().send, conn
        )
        if self._is_retryable():
            response = await self._retry_operation_async(request)
        else:
            response = await request()
        return response
