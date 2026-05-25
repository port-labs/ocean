from typing import TYPE_CHECKING

import httpx

from port_ocean.context.event import EventType, event
from port_ocean.exceptions.context import EventContextNotFoundError
from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.clients.port.retry_transport import TokenRetryTransport
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.ssl import get_ssl_context, SSLClientType

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient

# In case the framework sends more requests to port in parallel than allowed by the limits, a PoolTimeout exception will
# be raised.
# Raising defaults for the timeout, in addition to the limits, will allow request to wait for a connection for a longer
# period of time, before raising an exception.
# The max_connections value can't be too high, as it will cause the application to run out of memory.
# The max_keepalive_connections can't be too high, as it will cause the application to run out of available connections.
PORT_HTTP_MAX_CONNECTIONS_LIMIT = 100
PORT_HTTP_MAX_KEEP_ALIVE_CONNECTIONS = 50
PORT_HTTP_TIMEOUT = 60.0

PORT_HTTPX_TIMEOUT = httpx.Timeout(PORT_HTTP_TIMEOUT)
PORT_HTTPX_LIMITS = httpx.Limits(
    max_connections=PORT_HTTP_MAX_CONNECTIONS_LIMIT,
    max_keepalive_connections=PORT_HTTP_MAX_KEEP_ALIVE_CONNECTIONS,
)

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()

FIVE_MINUETS = 60 * 5

# Prefix for ocean info query params (ocean_info_event_type, ocean_info_resync_id)
OCEAN_INFO_PREFIX = "ocean_info_"


def _get_http_client_context(port_client: "PortClient") -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        ssl_context = get_ssl_context(SSLClientType.PORT)
        client = OceanAsyncClient(
            TokenRetryTransport,
            transport_kwargs={
                "port_client": port_client,
                "max_backoff_wait": FIVE_MINUETS,
                "base_delay": 0.3,
            },
            timeout=PORT_HTTPX_TIMEOUT,
            limits=PORT_HTTPX_LIMITS,
            verify=ssl_context,
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


def get_event_context_params() -> dict[str, str]:
    """Get ocean info query params when in an event context.

    Uses underscore prefix notation (ocean_info_event_type, ocean_info_resync_id).
    resyncId is only included for RESYNC events.
    """
    try:
        params: dict[str, str] = {f"{OCEAN_INFO_PREFIX}event_type": event.event_type}
        if event.event_type == EventType.RESYNC:
            params[f"{OCEAN_INFO_PREFIX}resync_id"] = event.id
        return params
    except EventContextNotFoundError:
        pass
    return {}


def handle_port_status_code(
    response: httpx.Response, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and response.is_error:
        escaped_response_text = response.text.replace("{", "{{").replace("}", "}}")
        error_message = f"Request failed with status code: {response.status_code}, Error: {escaped_response_text}"
        if response.status_code >= 500 and response.headers.get("x-trace-id"):
            logger.error(
                error_message,
                trace_id=response.headers.get("x-trace-id"),
            )
        else:
            logger.error(error_message)
    if should_raise:
        response.raise_for_status()
