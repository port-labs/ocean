from typing import Any, Callable, Coroutine, Optional, Union
import typing

import httpx
from port_ocean.helpers.retry import RetryConfig, RetryTransport


class ServiceNowRetryTransport(RetryTransport):
    """ServiceNow-specific retry behavior.

    Long rate-limit backoffs can outlive OAuth access tokens. Sleep first, then
    ask the authenticator for headers immediately before retrying. The
    authenticator decides whether those headers can come from cache or require
    a token refresh.
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
        self._auth_header_refresher = auth_header_refresher

    async def before_retry_after_sleep_async(
        self,
        request: httpx.Request,
        response: Optional[httpx.Response],
        sleep_time: float,
        attempt: int,
    ) -> Optional[httpx.Request]:
        if self._auth_header_refresher is None:
            return None

        headers = dict(request.headers)
        auth_headers = await self._auth_header_refresher()
        headers.update({key.lower(): value for key, value in auth_headers.items()})

        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=await self._read_request_body(request),
            extensions=request.extensions,
        )

    async def _read_request_body(self, request: httpx.Request) -> bytes:
        try:
            return request.content
        except httpx.RequestNotRead:
            if isinstance(request.stream, typing.AsyncIterable):
                await request.aread()
            else:
                request.read()
            return request.content
