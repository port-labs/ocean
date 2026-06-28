import typing
from typing import Any, Callable, Coroutine, Dict, Optional, Union

import httpx

from port_ocean.helpers.retry import RetryConfig, RetryTransport


class MendRetryTransport(RetryTransport):
    def __init__(
        self,
        wrapped_transport: Union[httpx.BaseTransport, httpx.AsyncBaseTransport],
        token_refresher: Optional[
            Callable[[], Coroutine[Any, Any, Dict[str, str]]]
        ] = None,
        retry_config: Optional[RetryConfig] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(wrapped_transport, retry_config=retry_config, **kwargs)
        self._token_refresher = token_refresher

    async def before_retry_async(
        self,
        request: httpx.Request,
        response: Optional[httpx.Response],
        sleep_time: float,
        attempt: int,
    ) -> Optional[httpx.Request]:
        if (
            self._token_refresher is None
            or response is None
            or response.status_code != 401
        ):
            return None
        fresh_headers = await self._token_refresher()
        fresh_lower = {k.lower(): v for k, v in fresh_headers.items()}

        try:
            content = request.content
        except httpx.RequestNotRead:
            if isinstance(request.stream, typing.AsyncIterable):
                await request.aread()
            else:
                request.read()
            content = request.content

        return httpx.Request(
            method=request.method,
            url=request.url,
            headers={**dict(request.headers), **fresh_lower},
            content=content,
            extensions=request.extensions,
        )
