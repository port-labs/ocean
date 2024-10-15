from asyncio import ensure_future
from typing import TYPE_CHECKING

import aiohttp
from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.helpers.retry import RetryRequestClass
from port_ocean.utils.signal import signal_handler

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient

# In case the framework sends more requests to port in parallel than allowed by the limits, a PoolTimeout exception will
# be raised.
# Raising defaults for the timeout, in addition to the limits, will allow request to wait for a connection for a longer
# period of time, before raising an exception.
# The max_connections value can't be too high, as it will cause the application to run out of memory.
# The max_keepalive_connections can't be too high, as it will cause the application to run out of available connections.
PORT_HTTP_MAX_CONNECTIONS_LIMIT = 200
PORT_HTTP_MAX_KEEP_ALIVE_CONNECTIONS = 50
PORT_HTTP_TIMEOUT = 60.0

TIMEOUT = aiohttp.ClientTimeout(total=PORT_HTTP_TIMEOUT)

_http_client: LocalStack[aiohttp.ClientSession] = LocalStack()


class PortRetryRequestClass(RetryRequestClass):
    RETRYABLE_ROUTES = frozenset(["/auth/access_token", "/entities/search"])

    def _is_retryable(self) -> bool:
        return super()._is_retryable() or any([route in self.url.path for route in self.RETRYABLE_ROUTES])


class OceanPortAsyncClient(aiohttp.ClientSession):
    def __init__(self, port_client: "PortClient", *args,
                 **kwargs):
        self._port_client = port_client
        super().__init__(*args, **kwargs)


def _get_http_client_context(port_client: "PortClient") -> aiohttp.ClientSession:
    client = _http_client.top
    if client is None:
        AIOHTTP_CONNECTOR = aiohttp.TCPConnector(limit=PORT_HTTP_MAX_CONNECTIONS_LIMIT, force_close=True)
        client = OceanPortAsyncClient(port_client, timeout=TIMEOUT, request_class=PortRetryRequestClass,
                                      connector=AIOHTTP_CONNECTOR,
                                      trust_env=True)
        _http_client.push(client)
        signal_handler.register(lambda: ensure_future(client.close()))
    return client


_port_internal_async_client: aiohttp.ClientSession = None  # type: ignore


def get_internal_http_client(port_client: "PortClient") -> aiohttp.ClientSession:
    global _port_internal_async_client
    if _port_internal_async_client is None:
        _port_internal_async_client = LocalProxy(
            lambda: _get_http_client_context(port_client)
        )

    return _port_internal_async_client


async def handle_status_code(
        response: aiohttp.ClientResponse, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and not response.ok:
        logger.error(
            f"Request failed with status code: {response.status}, Error: {await response.text()}"
        )
    if should_raise:
        response.raise_for_status()
