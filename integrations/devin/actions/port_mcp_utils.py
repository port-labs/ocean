"""Port MCP session credentials for Devin via `session_secrets`.

Devin org MCP plugins should declare headers like
`Authorization: Bearer ${PORT_MCP_ACCESS_TOKEN}`. Each run injects a
session-scoped secret so tokens never touch shared org secrets.
"""

from __future__ import annotations

from typing import Any

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

# Must match the placeholder name in the customer's Devin Port MCP plugin.
PORT_MCP_SESSION_SECRET_KEY = "PORT_MCP_ACCESS_TOKEN"


def _normalize_mcp_url(url: str) -> str:
    return url.rstrip("/")


def required_port_mcp_url() -> str:
    port_mcp_url = ocean.config.port.mcp_url
    if not port_mcp_url:
        raise ActionExecutionError("Port MCP URL is not configured for this integration")
    return _normalize_mcp_url(port_mcp_url)


def apply_port_mcp_session_secrets(
    body: dict[str, Any], run: IntegrationRun, enable_port_mcp: bool
) -> None:
    if not enable_port_mcp:
        return
    secrets = port_mcp_session_secrets(run)
    existing = [
        item
        for item in (body.get("session_secrets") or [])
        if item.get("key") != PORT_MCP_SESSION_SECRET_KEY
    ]
    body["session_secrets"] = [*existing, *secrets]


def port_mcp_session_secrets(run: IntegrationRun) -> list[dict[str, Any]]:
    access_token = get_run_access_token(run)
    if access_token is None:
        raise ActionExecutionError(
            "enablePortMcp requires executionIdentity on the workflow node "
            "(actor or service_account) and a portAccessToken on the claimed run"
        )
    return [
        {
            "key": PORT_MCP_SESSION_SECRET_KEY,
            "value": access_token,
            "sensitive": True,
        }
    ]