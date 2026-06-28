from http import HTTPStatus
from typing import Any, Callable, Coroutine, Mapping, Optional, Union
import typing

import httpx
from loguru import logger
from port_ocean.helpers.retry import RetryConfig, RetryTransport

from azure_devops.client.rate_limiter import (
    ADO_RATE_LIMIT_WINDOW_SECONDS,
    AzureDevOpsRateLimiter,
    LIMIT_HEADER,
    LIMIT_REMAINING_HEADER,
    LIMIT_RESET_HEADER,
    LIMIT_RETRY_AFTER_HEADER,
)


class AzureDevOpsRetryTransport(RetryTransport):
    """Azure DevOps-specific retry behavior.

    ADO sometimes returns 429 without enough useful headers to drive the generic
    retry backoff. When that happens, notify the shared limiter immediately so
    subsequent requests queue behind the cooldown, then retry after the fixed ADO
    cooldown window.
    """

    def __init__(
        self,
        wrapped_transport: Union[httpx.BaseTransport, httpx.AsyncBaseTransport],
        max_attempts: int = 10,
        max_backoff_wait: float = 60.0,
        base_delay: float = 0.1,
        jitter_ratio: float = 0.1,
        respect_retry_after_header: bool = True,
        retryable_methods: Optional[typing.Iterable[str]] = None,
        retry_status_codes: Optional[typing.Iterable[int]] = None,
        retry_config: Optional[RetryConfig] = None,
        logger: Optional[Any] = None,
        rate_limiter: Optional[AzureDevOpsRateLimiter] = None,
        auth_header_refresher: Optional[
            Callable[[], Coroutine[Any, Any, dict[str, str]]]
        ] = None,
    ) -> None:
        super().__init__(
            wrapped_transport=wrapped_transport,
            max_attempts=max_attempts,
            max_backoff_wait=max_backoff_wait,
            base_delay=base_delay,
            jitter_ratio=jitter_ratio,
            respect_retry_after_header=respect_retry_after_header,
            retryable_methods=retryable_methods,
            retry_status_codes=retry_status_codes,
            retry_config=retry_config,
            logger=logger,
        )
        self._rate_limiter = rate_limiter
        self._auth_header_refresher = auth_header_refresher

    async def after_retry_async(
        self,
        request: httpx.Request,
        response: httpx.Response,
        attempt: int,
    ) -> None:
        if self._rate_limiter is None:
            return

        await self._rate_limiter.update_from_headers(response.headers)
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            await self._rate_limiter.signal_throttle(
                ADO_RATE_LIMIT_WINDOW_SECONDS,
                reason="HTTP 429",
            )

    async def before_retry_async(
        self,
        request: httpx.Request,
        response: Optional[httpx.Response],
        sleep_time: float,
        attempt: int,
    ) -> Optional[httpx.Request]:
        if response is None and self._rate_limiter is not None:
            await self._rate_limiter.signal_throttle(
                ADO_RATE_LIMIT_WINDOW_SECONDS,
                reason="transport retry",
            )

        if self._auth_header_refresher is None:
            return None

        headers = dict(request.headers)
        fresh_headers = await self._auth_header_refresher()
        headers.update({k.lower(): v for k, v in fresh_headers.items()})

        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=await self._read_request_body(request),
            extensions=request.extensions,
        )

    async def _read_request_body(self, request: httpx.Request) -> bytes:
        try:
            content = request.content
        except httpx.RequestNotRead:
            if isinstance(request.stream, typing.AsyncIterable):
                await request.aread()
            else:
                request.read()
            content = request.content

        return content

    def _calculate_sleep(
        self,
        attempts_made: int,
        headers: Union[httpx.Headers, Mapping[str, str]],
        status_code: Optional[int] = None,
    ) -> float:
        if status_code in {HTTPStatus.TOO_MANY_REQUESTS, None}:
            return ADO_RATE_LIMIT_WINDOW_SECONDS
        return super()._calculate_sleep(attempts_made, headers, status_code)

    def _log_before_retry(
        self,
        request: httpx.Request,
        sleep_time: float,
        response: Optional[httpx.Response],
        error: Optional[Exception],
    ) -> None:
        if response and response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            logger.bind(
                remaining=response.headers.get(LIMIT_REMAINING_HEADER),
                limit=response.headers.get(LIMIT_HEADER),
                reset=response.headers.get(LIMIT_RESET_HEADER),
                retry_after=response.headers.get(LIMIT_RETRY_AFTER_HEADER),
                method=request.method,
                url=str(request.url),
                sleep_time=sleep_time,
            ).warning(
                f"Azure DevOps rate limit hit, retrying {request.method} {request.url} in {sleep_time}s"
            )
        elif response is None and error is not None:
            logger.bind(
                error_type=type(error).__name__,
                method=request.method,
                url=str(request.url),
                sleep_time=sleep_time,
            ).warning(
                f"Azure DevOps transport error hit, retrying {request.method} {request.url} in {sleep_time}s"
            )
        super()._log_before_retry(request, sleep_time, response, error)
