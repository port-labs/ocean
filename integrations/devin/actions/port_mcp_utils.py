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


def validate_port_mcp_secret_key(value: str) -> str:
    if not value.startswith("MCP_"):
        raise ValueError("portMcpSecretKey must start with MCP_")
    return value


def port_mcp_secret_key_from_config(integration_config: dict[str, Any]) -> str:
    """Session secret key from installation config; used only when enablePortMcp is true."""
    raw = integration_config.get("port_mcp_secret_key")
    if raw is None or raw == "":
        return DEFAULT_PORT_MCP_SESSION_SECRET_KEY
    if not isinstance(raw, str):
        raise ActionExecutionError(
            "portMcpSecretKey integration configuration must be a string"
        )
    try:
        return validate_port_mcp_secret_key(raw)
    except ValueError as error:
        raise ActionExecutionError(str(error)) from error


def apply_port_mcp_session_secrets(
    body: dict[str, Any],
    run: IntegrationRun,
    enable_port_mcp: bool,
    secret_key: str,
) -> None:
    if not enable_port_mcp:
        return
    secret_key = validate_port_mcp_secret_key(secret_key)
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