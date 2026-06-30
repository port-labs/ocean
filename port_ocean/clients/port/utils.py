import json
from typing import Any, TYPE_CHECKING

import httpx

from port_ocean.context.event import EventType, event
from port_ocean.exceptions.context import EventContextNotFoundError
from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.clients.port.retry_transport import TokenRetryTransport
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.ssl import resolve_verify_param

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
        client = OceanAsyncClient(
            TokenRetryTransport,
            transport_kwargs={
                "port_client": port_client,
                "max_backoff_wait": FIVE_MINUETS,
                "base_delay": 0.3,
            },
            timeout=PORT_HTTPX_TIMEOUT,
            limits=PORT_HTTPX_LIMITS,
            verify=resolve_verify_param(ocean.config.ssl.port),
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


def _format_error_value(error: Any) -> str | None:
    """Turn a Port API ``error`` field into a readable string."""
    if error is None:
        return None
    if isinstance(error, str):
        if error in ("[object Object]", "{}"):
            return None
        return error
    if isinstance(error, dict):
        if not error:
            return None
        name = error.get("name") or error.get("code")
        message = error.get("message")
        if name and message:
            return f"{name}: {message}"
        if message:
            return str(message)
        if name:
            return str(name)
        details = error.get("details")
        if details:
            return f"{name or 'error'}: {json.dumps(details, default=str)}"
        return json.dumps(error, default=str)
    return str(error)


def _is_unhelpful_error_value(error: Any) -> bool:
    return (
        error in (None, "", "[object Object]", "{}", {}) or error == "[object Object]"
    )


def format_port_error_response(response: httpx.Response) -> str:
    """Build a human-readable summary of a failed Port API response body."""
    text = response.text.strip()
    if not text:
        return "(empty response body)"

    try:
        body = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text

    if not isinstance(body, dict):
        return json.dumps(body, default=str)

    parts: list[str] = []

    message = body.get("message")
    if message not in (None, "", {}):
        if isinstance(message, str) and message.strip():
            parts.append(message.strip())
        else:
            parts.append(json.dumps(message, default=str))

    error_summary = _format_error_value(body.get("error"))
    if error_summary:
        parts.append(error_summary)

    for key in ("errors", "details"):
        value = body.get(key)
        if value not in (None, {}, []):
            parts.append(f"{key}={json.dumps(value, default=str)}")

    if parts:
        return " | ".join(parts)

    if body.get("ok") is False and _is_unhelpful_error_value(body.get("error")):
        return (
            "Port API returned ok=false without a detailed error message "
            "(the server failed to serialize the error object)"
        )

    return json.dumps(body, default=str)


def _build_port_error_log_message(response: httpx.Response, port_error: str) -> str:
    """Single-line message with request target — visible at default log levels."""
    target = "unknown request"
    if response.request is not None:
        target = f"{response.request.method} {response.request.url}"

    message = (
        f"Port request failed: {target} → HTTP {response.status_code} — {port_error}"
    )

    trace_id = response.headers.get("x-trace-id")
    if response.status_code >= 500 and trace_id:
        message += f" (trace_id={trace_id})"

    return message


def handle_port_status_code(
    response: httpx.Response, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and response.is_error:
        port_error = format_port_error_response(response)
        log_message = _build_port_error_log_message(response, port_error)
        log_kwargs: dict[str, Any] = {
            "status_code": response.status_code,
            "port_error": port_error,
            "response_body": response.text[:2000],
        }
        if response.request is not None:
            log_kwargs["method"] = response.request.method
            log_kwargs["url"] = str(response.request.url)

        trace_id = response.headers.get("x-trace-id")
        if trace_id:
            log_kwargs["trace_id"] = trace_id

        # opt(raw=True): message is final — port_error may contain JSON braces that
        # must not be interpreted as loguru format placeholders.
        logger.bind(**log_kwargs).opt(raw=True).error(log_message)
    if should_raise:
        response.raise_for_status()
