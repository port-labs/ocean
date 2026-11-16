"""Inject Port MCP bearer into Devin session_secrets (per-session user secrets)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

DEFAULT_PORT_MCP_SESSION_SECRET_KEY = "MCP_PORT_TOKEN"

_TOKEN_ERROR = (
    "enablePortMcp requires executionIdentity on the workflow node "
    "(actor or service_account) and a portAccessToken on the claimed run"
)


def port_mcp_secret_key(integration_config: dict[str, Any]) -> str:
    """Used when enablePortMcp is true; installation config types come from spec.json."""
    key = (
        integration_config.get("port_mcp_secret_key")
        or DEFAULT_PORT_MCP_SESSION_SECRET_KEY
    )
    if not key.startswith("MCP_"):
        raise ActionExecutionError("portMcpSecretKey must start with MCP_")
    return key


def apply_port_mcp_session_secrets(
    body: dict[str, Any],
    run: IntegrationRun,
    enable_port_mcp: bool,
    secret_key: str,
) -> None:
    if not enable_port_mcp:
        return
    access_token = get_run_access_token(run)
    if access_token is None:
        raise ActionExecutionError(_TOKEN_ERROR)
    existing = [
        item
        for item in (body.get("session_secrets") or [])
        if item.get("key") != secret_key
    ]
    body["session_secrets"] = [
        *existing,
        {
            "key": secret_key,
            "value": access_token,
            "sensitive": True,
        },
    ]


class PortMcpActionMixin(BaseModel):
    """Shared enablePortMcp inputs for create_session and send_message."""

    model_config = ConfigDict(extra="ignore")

    enablePortMcp: bool = False