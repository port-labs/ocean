from typing import TYPE_CHECKING

import httpx
from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.clients.port.retry_transport import TokenRetryTransport

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()


def _get_http_client_context(port_client: "PortClient") -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        client = httpx.AsyncClient(
            transport=TokenRetryTransport(
                port_client,
                httpx.AsyncHTTPTransport(),
                logger=logger,
            )
        )
        _http_client.push(client)

    return client


_port_internal_async_client: httpx.AsyncClient = None  # type: ignore


def get_internal_http_client(port_client: "PortClient") -> httpx.AsyncClient:
    global _port_internal_async_client
    if _port_internal_async_client is None:
        _port_internal_async_client = LocalProxy(
            lambda: _get_http_client_context(port_client)
        )

    return _port_internal_async_client


def handle_status_code(
    response: httpx.Response, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and response.is_error:
        logger.error(
            f"Request failed with status code: {response.status_code}, Error: {response.text}"
        )
    if should_raise:
        response.raise_for_status()
