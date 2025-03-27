import httpx
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryTransport

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()


def _get_http_client_context() -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        client = OceanAsyncClient(
            RetryTransport,
            timeout=ocean.config.client_timeout,
        )
        _http_client.push(client)

    return client


"""
Utilize this client for all outbound integration requests to the third-party application. It functions as a wrapper
around the httpx.AsyncClient, incorporating retry logic at the transport layer for handling retries on 5xx errors and
connection errors.

The client is instantiated lazily, only coming into existence upon its initial access. It should not be closed when in
use, as it operates as a singleton shared across all events in the thread. It also takes care of recreating the client
in scenarios such as the creation of a new event loop, such as when initiating a new thread.
"""
http_async_client: httpx.AsyncClient = LocalProxy(lambda: _get_http_client_context())  # type: ignore
