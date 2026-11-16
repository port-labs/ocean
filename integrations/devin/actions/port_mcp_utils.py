"""Inject Port MCP bearer into Devin create/send via session_secrets."""

from __future__ import annotations

from typing import Any

from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

PORT_MCP_SESSION_SECRET_KEY = "PORT_MCP_ACCESS_TOKEN"


def apply_port_mcp_session_secrets(
    body: dict[str, Any], run: IntegrationRun, enable_port_mcp: bool
) -> None:
    if not enable_port_mcp:
        return
    access_token = get_run_access_token(run)
    if access_token is None:
        raise ActionExecutionError(
            "enablePortMcp requires executionIdentity on the workflow node "
            "(actor or service_account) and a portAccessToken on the claimed run"
        )
    existing = [
        item
        for item in (body.get("session_secrets") or [])
        if item.get("key") != PORT_MCP_SESSION_SECRET_KEY
    ]
    body["session_secrets"] = [
        *existing,
        {
            "key": PORT_MCP_SESSION_SECRET_KEY,
            "value": access_token,
            "sensitive": True,
        },
    ]