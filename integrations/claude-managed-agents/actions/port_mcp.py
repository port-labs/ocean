from __future__ import annotations

from typing import Any

from anthropic.types.beta import (
    BetaManagedAgentsAgent,
    BetaManagedAgentsSession,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import (
    get_run_access_token,
    resolve_port_mcp_url,
)
from clients.anthropic_client import AnthropicClient
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

PORT_MCP_SERVER_NAME = "port"
PORT_IDENTITY_ID_KEY = "port_identity_id"
PORT_MCP_FAILED_STATUS_LABEL = "Port MCP failed"
_PORT_TOOLSET = {
    "type": "mcp_toolset",
    "mcp_server_name": PORT_MCP_SERVER_NAME,
    "default_config": {"permission_policy": {"type": "always_allow"}},
}


def _fail(message: str) -> ActionExecutionError:
    return ActionExecutionError(message, status_label=PORT_MCP_FAILED_STATUS_LABEL)


def _merge_lists_by_key(list1: list[Any], list2: list[Any], key: str) -> list[Any]:
    return list({d[key.rstrip("/")]: d for d in list1 + list2 if key in d}.values())


def apply_port_mcp(
    config: dict[str, Any] | None = None,
    agent: BetaManagedAgentsAgent | None = None,
) -> dict[str, Any]:
    """Attach the Port MCP server + toolset to agent config. Pass ``current``
    on update to keep existing tools/mcp_servers; ``enabled=False`` no-ops."""
    port_mcp_url = resolve_port_mcp_url(ocean.config.port.base_url)
    agent_servers = agent.mcp_servers if agent else []
    agent_tools = agent.tools if agent else []
    agent_tools = _as_list(config.get("tools"))
    if not _has_port_server(servers, url):
        servers.append({"type": "url", "name": PORT_MCP_SERVER_NAME, "url": url})
    if not any(
        isinstance(t, dict) and t.get("mcp_server_name") == PORT_MCP_SERVER_NAME
        for t in tools
    ):
        tools.append(dict(_PORT_TOOLSET))
    return {**config, "mcp_servers": servers, "tools": tools}


def _claim(run: IntegrationRun) -> tuple[str | None, str | None]:
    """Return (access_token, identity_id) the run acts as, or (x, None) if the
    run has no execution identity (e.g. a classic self-service action run)."""
    try:
        token = get_run_access_token(run)
    except ActionExecutionError as error:
        raise _fail(str(error)) from error
    if not isinstance(run, WorkflowNodeRun) or run.execution_identity is None:
        return token, None
    return token, run.execution_identity.identifier


async def _find(pages: Any, match: Any) -> Any:
    async for batch in pages:
        for item in batch:
            if match(item):
                return item
    return None


async def _upsert_vault(
    client: Any, identity_id: str, access_token: str, vault_name: str | None
) -> str:
    """Find or create the user's vault, then (re)mint its Port MCP credential."""
    name = vault_name or f"port-mcp-{identity_id}"
    vault = await _find(
        client.paginate(client.beta.vaults.list(include_archived=False)),
        lambda v: getattr(v, "display_name", None) == name,
    )
    if vault is None:
        logger.info(f"Creating Port MCP vault '{name}'")
        vault = await client.beta.vaults.create(
            display_name=name, metadata={PORT_IDENTITY_ID_KEY: identity_id}
        )

    credential = await _find(
        client.paginate(client.beta.vaults.credentials.list(vault_id=vault.id)),
        lambda c: not getattr(c, "archived_at", None)
        and getattr(c, "display_name", None) == "port-mcp",
    )
    auth = {
        "type": "static_bearer",
        "token": access_token,
        "mcp_server_url": resolve_port_mcp_url(ocean.config.port.base_url),
    }
    if credential is None:
        await client.beta.vaults.credentials.create(
            vault.id, auth=auth, display_name="port-mcp"
        )
    else:
        await client.beta.vaults.credentials.update(
            credential.id, vault_id=vault.id, auth=auth
        )
    return vault.id


async def attach_port_mcp_vault(
    client: Any,
    run: IntegrationRun,
    *,
    environment_id: str,
    config: dict[str, Any],
    vault_name: str | None = None,
) -> dict[str, Any]:
    """Wire a per-user vault into a new session's config; no-op without a
    Port access token/identity on the run."""
    token, identity_id = _claim(run)
    if not token or not identity_id:
        return config

    vault_id = await _upsert_vault(client, identity_id, token, vault_name)
    raw_metadata = config.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    metadata[PORT_IDENTITY_ID_KEY] = identity_id
    vault_ids = _as_list(config.get("vault_ids"))
    if vault_id not in vault_ids:
        vault_ids.append(vault_id)
    return {**config, "metadata": metadata, "vault_ids": vault_ids}


async def reauthorize_port_mcp_session(
    client: AnthropicClient,
    run: IntegrationRun,
    session: BetaManagedAgentsSession,
    vault_name: str | None = None,
) -> None:
    """Remint the vault credential for a continued session, verifying the
    run's identity still matches the session's owner. No-op if unowned."""
    owner = session.metadata.get(PORT_IDENTITY_ID_KEY)
    if owner != run.execution_identity.identifier:
        raise _fail(
            f"Cannot continue session {session.id}: owned by {owner}, "
            f"run is {run.execution_identity.identifier}"
        )

    await _upsert_vault(
        client, run.execution_identity.identifier, get_run_access_token(run), vault_name
    )
