from __future__ import annotations

import time
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import (
    get_run_access_token,
    resolve_port_mcp_url,
)
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

PORT_MCP_SERVER_NAME = "port"
PORT_IDENTITY_ID_KEY = "port_identity_id"
PORT_MCP_FAILED_STATUS_LABEL = "Port MCP failed"
_TOOLSET = {
    "type": "mcp_toolset",
    "mcp_server_name": PORT_MCP_SERVER_NAME,
    "default_config": {"permission_policy": {"type": "always_allow"}},
}
_TTL = 300.0
_ALLOWED_ENVIRONMENTS: dict[tuple[str, str], float] = {}
_AGENTS_WITH_PORT_MCP: dict[str, tuple[bool, float]] = {}


def _fail(message: str) -> ActionExecutionError:
    return ActionExecutionError(message, status_label=PORT_MCP_FAILED_STATUS_LABEL)


def _mcp_url() -> str:
    return resolve_port_mcp_url(ocean.config.port.base_url)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _is_port_server(server: Any, url: str) -> bool:
    return (
        isinstance(server, dict)
        and isinstance(server.get("url"), str)
        and server["url"].rstrip("/") == url
    )


def apply_port_mcp_to_agent_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _mcp_url()
    servers, tools = _as_list(config.get("mcp_servers")), _as_list(config.get("tools"))
    if not any(_is_port_server(server, url) for server in servers):
        servers.append({"type": "url", "name": PORT_MCP_SERVER_NAME, "url": url})
    if not any(
        isinstance(tool, dict) and tool.get("mcp_server_name") == PORT_MCP_SERVER_NAME
        for tool in tools
    ):
        tools.append(dict(_TOOLSET))
    return {**config, "mcp_servers": servers, "tools": tools}


def environment_allows_port_mcp(environment: Any, mcp_url: str) -> bool:
    config = getattr(environment, "config", None)
    networking = getattr(config, "networking", None)
    limited = (
        getattr(config, "type", None) == "cloud"
        and getattr(networking, "type", None) == "limited"
        and not getattr(networking, "allow_mcp_servers", False)
    )
    host = urlparse(mcp_url).hostname or ""
    hosts = getattr(networking, "allowed_hosts", None) or []
    return not limited or any(fnmatchcase(host, pattern.lower()) for pattern in hosts)


async def ensure_environment_allows_port_mcp(
    client: Any, environment_id: str, mcp_url: str | None = None
) -> None:
    url = mcp_url or _mcp_url()
    key = (environment_id, url)
    if _ALLOWED_ENVIRONMENTS.get(key, 0) > time.monotonic():
        return
    environment = await client.get_environment(environment_id)
    if not environment_allows_port_mcp(environment, url):
        host = urlparse(url).hostname
        raise _fail(f"Environment {environment_id} blocks Port MCP host {host!r}")
    _ALLOWED_ENVIRONMENTS[key] = time.monotonic() + _TTL


async def agent_uses_port_mcp(client: Any, agent_id: str) -> bool:
    cached = _AGENTS_WITH_PORT_MCP.get(agent_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    url = _mcp_url()
    servers = getattr(await client.get_agent(agent_id), "mcp_servers", None)
    has = any(_is_port_server(server, url) for server in _as_list(servers))
    _AGENTS_WITH_PORT_MCP[agent_id] = (has, time.monotonic() + _TTL)
    return has


async def _first(pages: Any, match: Any) -> Any:
    async for batch in pages:
        found = next((item for item in batch if match(item)), None)
        if found:
            return found
    return None


async def ensure_port_mcp_vault(
    client: Any,
    identity_id: str,
    access_token: str,
    vault_name: str | None = None,
) -> str:
    name = vault_name or f"port-mcp-{identity_id}"
    vault = await _first(
        client.list_vaults(), lambda item: getattr(item, "display_name", None) == name
    )
    if vault is None:
        logger.info(f"Creating Port MCP vault '{name}'")
        vault = await client.create_vault(
            name, metadata={PORT_IDENTITY_ID_KEY: identity_id}
        )
    credential = await _first(
        client.list_vault_credentials(vault.id),
        lambda item: not getattr(item, "archived_at", None)
        and getattr(item, "display_name", None) == "port-mcp",
    )
    auth = {
        "type": "static_bearer",
        "token": access_token,
        "mcp_server_url": _mcp_url(),
    }
    if credential is None:
        await client.create_vault_credential(
            vault.id, auth=auth, display_name="port-mcp"
        )
    else:
        await client.update_vault_credential(vault.id, credential.id, auth=auth)
    return vault.id


def _claim(run: IntegrationRun) -> tuple[str | None, str | None]:
    try:
        token = get_run_access_token(run)
    except ActionExecutionError as error:
        raise _fail(str(error)) from error
    identity = (
        run.execution_identity
        if isinstance(run, WorkflowNodeRun) and isinstance(run.execution_identity, dict)
        else {}
    )
    identifier = identity.get("identifier")
    return token, identifier if isinstance(identifier, str) else None


async def prepare_port_mcp_session_config(
    client: Any,
    run: IntegrationRun,
    environment_id: str,
    config: dict[str, Any],
    vault_name: str | None = None,
) -> dict[str, Any]:
    token, identity_id = _claim(run)
    if not token or not identity_id:
        return config
    await ensure_environment_allows_port_mcp(client, environment_id)
    vault_id = await ensure_port_mcp_vault(client, identity_id, token, vault_name)
    metadata = (
        dict(config["metadata"]) if isinstance(config.get("metadata"), dict) else {}
    )
    metadata[PORT_IDENTITY_ID_KEY] = identity_id
    vault_ids = _as_list(config.get("vault_ids"))
    if vault_id not in vault_ids:
        vault_ids.append(vault_id)
    return {**config, "metadata": metadata, "vault_ids": vault_ids}


async def refresh_port_mcp_session(
    client: Any, run: IntegrationRun, session: Any, vault_name: str | None = None
) -> None:
    metadata = getattr(session, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    owner = metadata.get(PORT_IDENTITY_ID_KEY)
    if not isinstance(owner, str):
        return
    token, identity_id = _claim(run)
    if not token or not identity_id:
        raise _fail(
            f"Cannot continue session {session.id}: owned by {owner} "
            "without an execution identity"
        )
    if owner != identity_id:
        raise _fail(
            f"Cannot continue session {session.id}: owned by {owner}, "
            f"run is {identity_id}"
        )
    vault_id = await ensure_port_mcp_vault(client, identity_id, token, vault_name)
    if vault_id not in _as_list(getattr(session, "vault_ids", None)):
        raise _fail(f"Session {session.id} missing Port MCP vault {vault_id}")
