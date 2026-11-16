"""Rotate Devin org secret MCP_PORT_TOKEN for Port MCP access."""

from __future__ import annotations

import asyncio
from typing import Any

from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from pydantic import BaseModel, ConfigDict

from clients.devin_client import DevinClient

DEFAULT_PORT_MCP_ORG_SECRET_KEY = "MCP_PORT_TOKEN"

_org_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()

_TOKEN_ERROR = (
    "enablePortMcp requires executionIdentity on the workflow node "
    "(actor or service_account) and a portAccessToken on the claimed run"
)


def _port_mcp_lock_key(org_id: str, secret_key: str) -> str:
    return f"{org_id}:{secret_key}"


async def _org_lock(lock_key: str) -> asyncio.Lock:
    async with _locks_guard:
        lock = _org_locks.get(lock_key)
        if lock is None:
            lock = asyncio.Lock()
            _org_locks[lock_key] = lock
        return lock


def validate_port_mcp_secret_key(value: str) -> str:
    if not value.startswith("MCP_"):
        raise ValueError("portMcpSecretKey must start with MCP_")
    return value


def _require_port_mcp_token(run: IntegrationRun) -> str:
    access_token = get_run_access_token(run)
    if access_token is None:
        raise ActionExecutionError(_TOKEN_ERROR)
    return access_token


def port_mcp_secret_key_from_config(
    integration_config: dict[str, Any],
) -> str:
    """Secret key from installation config; used only when enablePortMcp is true."""
    raw = integration_config.get("port_mcp_secret_key")
    if raw is None or raw == "":
        return DEFAULT_PORT_MCP_ORG_SECRET_KEY
    if not isinstance(raw, str):
        raise ActionExecutionError(
            "portMcpSecretKey integration configuration must be a string"
        )
    try:
        return validate_port_mcp_secret_key(raw)
    except ValueError as error:
        raise ActionExecutionError(str(error)) from error


async def rotate_port_mcp_org_secret(
    client: DevinClient,
    run: IntegrationRun,
    enable_port_mcp: bool,
    secret_key: str = DEFAULT_PORT_MCP_ORG_SECRET_KEY,
) -> str | None:
    if not enable_port_mcp:
        return None
    secret_key = validate_port_mcp_secret_key(secret_key)
    jwt = _require_port_mcp_token(run)
    async with await _org_lock(_port_mcp_lock_key(client.org_id, secret_key)):
        existing_id = await client.find_secret_id_by_key(secret_key)
        if existing_id is not None:
            await client.delete_secret(existing_id)
        created = await client.create_secret(secret_key, jwt)
        secret_id = created.get("secret_id")
        if not isinstance(secret_id, str):
            raise ActionExecutionError(
                f"Devin did not return secret_id when creating {secret_key}"
            )
        return secret_id


class PortMcpActionMixin(BaseModel):
    """Shared enablePortMcp inputs for create_session and send_message."""

    model_config = ConfigDict(extra="ignore")

    enablePortMcp: bool = False


def merge_port_mcp_secret_id(body: dict[str, Any], secret_id: str | None) -> None:
    if secret_id is None:
        return
    existing = list(body.get("secret_ids") or [])
    body["secret_ids"] = list(dict.fromkeys([*existing, secret_id]))