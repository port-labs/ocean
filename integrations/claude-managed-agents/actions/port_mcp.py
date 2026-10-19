from __future__ import annotations

import time
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import decrypt_run_access_token
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

PORT_MCP_METADATA_KEY = "port_mcp"
PORT_MCP_METADATA_VALUE = "managed"
PORT_MCP_SERVER_NAME = "port"
DEFAULT_PORT_MCP_URL = "https://mcp.port.io/v1"
PORT_IDENTITY_TYPE_KEY = "port_identity_type"
PORT_IDENTITY_ID_KEY = "port_identity_id"
PORT_MCP_CREDENTIAL_NAME = "port-mcp"
PORT_MCP_FAILED_STATUS_LABEL = "Port MCP failed"

_ENVIRONMENT_CACHE_TTL_SECONDS = 300.0
_ALLOWED_ENVIRONMENTS: dict[tuple[str, str], float] = {}

_PORT_MCP_TOOLSET: dict[str, Any] = {
    "type": "mcp_toolset",
    "mcp_server_name": PORT_MCP_SERVER_NAME,
    "default_config": {"permission_policy": {"type": "always_allow"}},
}


def resolve_port_mcp_url(api_base_url: str | None = None) -> str:
    """Derive the matching Port MCP endpoint from the configured Port API URL."""
    if not api_base_url:
        return DEFAULT_PORT_MCP_URL
    parsed = urlparse(api_base_url)
    legacy_host = {
        "api.getport.io": "mcp.port.io",
        "api.us.getport.io": "mcp.us.port.io",
    }.get(parsed.hostname or "")
    if legacy_host:
        netloc = f"{legacy_host}:{parsed.port}" if parsed.port else legacy_host
        return f"{parsed.scheme or 'https'}://{netloc}/v1"
    if not parsed.hostname or not parsed.hostname.startswith("api."):
        return DEFAULT_PORT_MCP_URL
    hostname = f"mcp.{parsed.hostname.removeprefix('api.')}"
    netloc = f"{hostname}:{parsed.port}" if parsed.port else hostname
    return f"{parsed.scheme or 'https'}://{netloc}/v1"


def _port_mcp_url() -> str:
    try:
        return resolve_port_mcp_url(getattr(ocean.config.port, "base_url", None))
    except Exception:
        return DEFAULT_PORT_MCP_URL


def port_mcp_enabled(value: Any) -> bool | None:
    """Return the flag, or None when the value is not a boolean, 0/1, or true/1/yes."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if isinstance(value, int) and value in (0, 1):
        return value == 1
    return None


def is_port_mcp_managed(metadata: Any) -> bool:
    return (
        isinstance(metadata, dict)
        and metadata.get(PORT_MCP_METADATA_KEY) == PORT_MCP_METADATA_VALUE
    )


def _dict_field(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _list_field(config: dict[str, Any], key: str) -> list[Any]:
    value = config.get(key)
    return list(value) if isinstance(value, list) else []


def apply_port_mcp_to_agent_config(config: dict[str, Any]) -> dict[str, Any]:
    working = dict(config)
    metadata = _dict_field(working, "metadata")
    metadata[PORT_MCP_METADATA_KEY] = PORT_MCP_METADATA_VALUE
    working["metadata"] = metadata

    servers = _list_field(working, "mcp_servers")
    if not any(
        isinstance(server, dict) and server.get("name") == PORT_MCP_SERVER_NAME
        for server in servers
    ):
        servers.append(
            {"type": "url", "name": PORT_MCP_SERVER_NAME, "url": _port_mcp_url()}
        )
    working["mcp_servers"] = servers

    tools = _list_field(working, "tools")
    if not any(
        isinstance(tool, dict)
        and tool.get("type") == "mcp_toolset"
        and tool.get("mcp_server_name") == PORT_MCP_SERVER_NAME
        for tool in tools
    ):
        tools.append(dict(_PORT_MCP_TOOLSET))
    working["tools"] = tools
    return working


def environment_allows_port_mcp(environment: Any, mcp_url: str) -> bool:
    config = getattr(environment, "config", None)
    if getattr(config, "type", None) != "cloud":
        return True

    networking = getattr(config, "networking", None)
    if getattr(networking, "type", None) != "limited":
        return True
    if getattr(networking, "allow_mcp_servers", False):
        return True

    host = urlparse(mcp_url).hostname
    return bool(host) and any(
        fnmatchcase(host, pattern.lower())
        for pattern in (getattr(networking, "allowed_hosts", None) or [])
    )


async def ensure_environment_allows_port_mcp(
    client: Any,
    environment_id: str,
    mcp_url: str | None = None,
) -> None:
    url = mcp_url or _port_mcp_url()
    cache_key = (environment_id, url)
    now = time.monotonic()
    if _ALLOWED_ENVIRONMENTS.get(cache_key, 0) > now:
        return

    environment = await client.get_environment(environment_id)
    if not environment_allows_port_mcp(environment, url):
        raise ActionExecutionError(
            f"Environment {environment_id} blocks Port MCP host "
            f"{urlparse(url).hostname!r}. Add it to networking.allowed_hosts, "
            "or set allow_mcp_servers=true.",
            status_label=PORT_MCP_FAILED_STATUS_LABEL,
        )
    _ALLOWED_ENVIRONMENTS[cache_key] = now + _ENVIRONMENT_CACHE_TTL_SECONDS


async def ensure_port_mcp_vault(
    client: Any,
    identity_type: str,
    identity_id: str,
    access_token: str,
) -> str:
    """Get or create the identity vault and rotate its Port MCP bearer token."""
    name = f"port-mcp-{identity_type}-{identity_id}"
    vault = None
    async for batch in client.list_vaults():
        vault = next(
            (item for item in batch if getattr(item, "display_name", None) == name),
            None,
        )
        if vault:
            break
    if vault is None:
        logger.info(f"Creating Port MCP vault '{name}'")
        vault = await client.create_vault(
            name,
            metadata={
                PORT_MCP_METADATA_KEY: PORT_MCP_METADATA_VALUE,
                PORT_IDENTITY_TYPE_KEY: identity_type,
                PORT_IDENTITY_ID_KEY: identity_id,
            },
        )

    existing = None
    async for batch in client.list_vault_credentials(vault.id):
        existing = next(
            (
                credential
                for credential in batch
                if not getattr(credential, "archived_at", None)
                and getattr(credential, "display_name", None)
                == PORT_MCP_CREDENTIAL_NAME
            ),
            None,
        )
        if existing:
            break

    if existing is None:
        await client.create_vault_credential(
            vault.id,
            auth={
                "type": "static_bearer",
                "token": access_token,
                "mcp_server_url": _port_mcp_url(),
            },
            display_name=PORT_MCP_CREDENTIAL_NAME,
            metadata={PORT_MCP_METADATA_KEY: PORT_MCP_METADATA_VALUE},
        )
    else:
        await client.update_vault_credential(
            vault.id,
            existing.id,
            auth={
                "type": "static_bearer",
                "token": access_token,
                "mcp_server_url": _port_mcp_url(),
            },
        )
    return vault.id


def _port_mcp_claim(run: IntegrationRun) -> tuple[str, str, str] | None:
    identity = (
        run.execution_identity
        if isinstance(run, WorkflowNodeRun) and isinstance(run.execution_identity, dict)
        else None
    )
    if not identity:
        return None

    identity_type = identity.get("type")
    identity_id = identity.get("identifier")
    if identity_type not in ("actor", "service_account") or not isinstance(
        identity_id, str
    ):
        raise ActionExecutionError(
            "Port-managed MCP requires executionIdentity actor/service_account "
            "with identifier",
            status_label=PORT_MCP_FAILED_STATUS_LABEL,
        )

    try:
        access_token = decrypt_run_access_token(run)
    except ActionExecutionError as error:
        raise ActionExecutionError(
            str(error), status_label=PORT_MCP_FAILED_STATUS_LABEL
        ) from error
    if not access_token:
        raise ActionExecutionError(
            "Port-managed MCP requires portAccessToken when executionIdentity is set",
            status_label=PORT_MCP_FAILED_STATUS_LABEL,
        )
    return identity_type, identity_id, access_token


async def prepare_port_mcp_session_config(
    client: Any,
    run: IntegrationRun,
    environment_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    claim = _port_mcp_claim(run)
    if not claim:
        return config
    identity_type, identity_id, access_token = claim

    await ensure_environment_allows_port_mcp(client, environment_id)
    vault_id = await ensure_port_mcp_vault(
        client, identity_type, identity_id, access_token
    )

    working = dict(config)
    metadata = _dict_field(working, "metadata")
    metadata.update(
        {
            PORT_MCP_METADATA_KEY: PORT_MCP_METADATA_VALUE,
            PORT_IDENTITY_TYPE_KEY: identity_type,
            PORT_IDENTITY_ID_KEY: identity_id,
        }
    )
    working["metadata"] = metadata
    vault_ids = _list_field(working, "vault_ids")
    if vault_id not in vault_ids:
        vault_ids.append(vault_id)
    working["vault_ids"] = vault_ids
    return working


async def refresh_port_mcp_session(
    client: Any, run: IntegrationRun, session: Any
) -> None:
    metadata = (
        session.metadata if isinstance(getattr(session, "metadata", None), dict) else {}
    )
    owner = (
        metadata.get(PORT_IDENTITY_TYPE_KEY),
        metadata.get(PORT_IDENTITY_ID_KEY),
    )
    if owner == (None, None):
        return
    claim = _port_mcp_claim(run)
    if not claim:
        raise ActionExecutionError(
            f"Cannot continue session {session.id}: owned by {owner[0]}:{owner[1]} "
            "without an execution identity",
            status_label=PORT_MCP_FAILED_STATUS_LABEL,
        )
    identity_type, identity_id, access_token = claim
    if owner != (identity_type, identity_id):
        raise ActionExecutionError(
            f"Cannot continue session {session.id}: owned by {owner[0]}:{owner[1]}, "
            f"run is {identity_type}:{identity_id}",
            status_label=PORT_MCP_FAILED_STATUS_LABEL,
        )

    vault_id = await ensure_port_mcp_vault(
        client, identity_type, identity_id, access_token
    )
    if vault_id not in (getattr(session, "vault_ids", None) or []):
        raise ActionExecutionError(
            f"Session {session.id} missing Port MCP vault {vault_id}",
            status_label=PORT_MCP_FAILED_STATUS_LABEL,
        )
