from asyncio import ensure_future

import aiohttp
from aiohttp import ClientTimeout
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import RetryRequestClass
from port_ocean.utils.signal import signal_handler

_http_client: LocalStack[aiohttp.ClientSession] = LocalStack()


def _get_http_client_context() -> aiohttp.ClientSession:
    client = _http_client.top
    if client is None:
        client = aiohttp.ClientSession(request_class=RetryRequestClass,
                                       timeout=ClientTimeout(total=ocean.config.client_timeout))
        _http_client.push(client)
        signal_handler.register(lambda: ensure_future(client.close()))

    return client


"""
Utilize this client for all outbound integration requests to the third-party application. It functions as a wrapper 
around the aiohttp.ClientSession, incorporating retry logic at the transport layer for handling retries on 5xx errors and
connection errors.

The client is instantiated lazily, only coming into existence upon its initial access. It should not be closed when in
use, as it operates as a singleton shared across all events in the thread. It also takes care of recreating the client
in scenarios such as the creation of a new event loop, such as when initiating a new thread.
"""
http_async_client: aiohttp.ClientSession = LocalProxy(lambda: _get_http_client_context())  # type: ignore
