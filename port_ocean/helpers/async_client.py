from typing import Any, Type

import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryTransport, RetryConfig
from port_ocean.helpers.stream import Stream


class OceanAsyncClient(httpx.AsyncClient):
    """
    This class is a wrapper around httpx.AsyncClient that uses a custom transport class.
    This is done to allow passing our custom transport class to the AsyncClient constructor while still allowing
    all the default AsyncClient behavior that is changed when passing a custom transport instance.
    """

    def __init__(
        self,
        transport_class: Type[RetryTransport] = RetryTransport,
        transport_kwargs: dict[str, Any] | None = None,
        retry_config: RetryConfig | None = None,
        **kwargs: Any,
    ):
        self._transport_kwargs = transport_kwargs
        self._transport_class = transport_class
        self._retry_config = retry_config
        super().__init__(**kwargs)

    def _init_transport(  # type: ignore[override]
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        **kwargs: Any,
    ) -> httpx.AsyncBaseTransport:
        if transport is not None:
            return super()._init_transport(transport=transport, **kwargs)

        return self._transport_class(
            wrapped_transport=httpx.AsyncHTTPTransport(**kwargs),
            retry_config=self._retry_config,
            logger=logger,
            **(self._transport_kwargs or {}),
        )

    def _init_proxy_transport(  # type: ignore[override]
        self, proxy: httpx.Proxy, **kwargs: Any
    ) -> httpx.AsyncBaseTransport:
        return self._transport_class(
            wrapped_transport=httpx.AsyncHTTPTransport(proxy=proxy, **kwargs),
            retry_config=self._retry_config,
            logger=logger,
            **(self._transport_kwargs or {}),
        )

    async def get_stream(self, url: str, **kwargs: Any) -> Stream:
        req = self.build_request("GET", url, **kwargs)
        response = await self.send(req, stream=True)
        response.raise_for_status()
        return Stream(response)
