from typing import Any, Callable, Type

import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryTransport


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
        **kwargs: Any,
    ):
        self._transport_kwargs = transport_kwargs
        self._transport_class = transport_class
        super().__init__(**kwargs)

    def _init_transport(  # type: ignore[override]
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        app: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> httpx.AsyncBaseTransport:
        if transport is not None or app is not None:
            return super()._init_transport(transport=transport, app=app, **kwargs)

        return self._transport_class(
            wrapped_transport=httpx.AsyncHTTPTransport(
                **kwargs,
            ),
            logger=logger,
            **(self._transport_kwargs or {}),
        )

    def _init_proxy_transport(  # type: ignore[override]
        self, proxy: httpx.Proxy, **kwargs: Any
    ) -> httpx.AsyncBaseTransport:
        return self._transport_class(
            wrapped_transport=httpx.AsyncHTTPTransport(
                proxy=proxy,
                **kwargs,
            ),
            logger=logger,
            **(self._transport_kwargs or {}),
        )
