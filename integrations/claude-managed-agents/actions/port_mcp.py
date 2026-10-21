from __future__ import annotations

from typing import Any, cast

from anthropic.types.beta import (
    BetaManagedAgentsAgent,
    BetaManagedAgentsSession,
)
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)
from anthropic.types.beta.beta_managed_agents_mcp_toolset import (
    BetaManagedAgentsMCPToolset,
    BetaManagedAgentsMCPToolsetDefaultConfig,
)
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import (
    get_run_access_token,
    resolve_port_mcp_url,
)
from clients.anthropic_client import AnthropicClient
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

PORT_MCP_SERVER_NAME = "port"
PORT_IDENTITY_ID_KEY = "port_identity_id"
_PORT_TOOLSET = BetaManagedAgentsMCPToolset(
    type="mcp_toolset",
    mcp_server_name=PORT_MCP_SERVER_NAME,
    default_config=BetaManagedAgentsMCPToolsetDefaultConfig(
        permission_policy={"type": "always_allow"}
    ),
)


def _normalize_port_mcp_url(url: str) -> str:
    return url.replace("getport", "port").rstrip("/")


def _merge_mcp_servers_by_url(
    list1: list[BetaManagedAgentsMCPServerURLDefinition],
    list2: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({_normalize_port_mcp_url(d.url): d for d in list1 + list2}.values())


async def is_agent_configured_with_port_mcp(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> bool:
    port_mcp_url = resolve_port_mcp_url(ocean.config.port.base_url)
    return any(
        _normalize_port_mcp_url(s.url) == _normalize_port_mcp_url(port_mcp_url)
        for s in mcp_servers
    )


def attach_port_mcp_settings_to_agent_config(
    proposed_config: dict[str, Any],
    exitsing_agent: BetaManagedAgentsAgent | None = None,
) -> dict[str, Any]:
    """Attach the Port MCP server + toolset to agent config. Pass ``current``
    on update to keep existing tools/mcp_servers; ``enabled=False`` no-ops."""
    port_mcp_url = resolve_port_mcp_url(ocean.config.port.base_url)
    agent_servers = exitsing_agent.mcp_servers if exitsing_agent else []
    agent_tools = exitsing_agent.tools if exitsing_agent else []
    mcp_servers = _merge_mcp_servers_by_url(
        agent_servers,
        cast(
            list[BetaManagedAgentsMCPServerURLDefinition],
            proposed_config.get("mcp_servers", []),
        ),
    )
    if not is_agent_configured_with_port_mcp(mcp_servers):
        mcp_servers.append(
            BetaManagedAgentsMCPServerURLDefinition(
                type="url", name=PORT_MCP_SERVER_NAME, url=port_mcp_url
            )
        )
        return {
            **proposed_config,
            "mcp_servers": mcp_servers,
            "tools": [*agent_tools, _PORT_TOOLSET],
        }
    return proposed_config


async def _upsert_vault(
    client: AnthropicClient, identity_id: str, access_token: str, vault_name: str | None
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


async def attach_port_mcp_vault_to_session_config(
    client: AnthropicClient,
    run: WorkflowNodeRun,
    *,
    config: dict[str, Any],
    vault_name: str | None = None,
) -> dict[str, Any]:
    """Wire a per-user vault into a new session's config; no-op without a
    Port access token/identity on the run."""
    vault_id = await _upsert_vault(
        client, run.execution_identity.identifier, get_run_access_token(run), vault_name
    )
    return {
        **config,
        "metadata": {
            **config.get("metadata", {}),
            PORT_IDENTITY_ID_KEY: run.execution_identity.identifier,
        },
        "vault_ids": [*config.get("vault_ids", []), vault_id],
    }


async def reauthorize_port_mcp_session(
    client: AnthropicClient,
    run: WorkflowNodeRun,
    session: BetaManagedAgentsSession,
    vault_name: str | None = None,
) -> None:
    """Remint the vault credential for a continued session, verifying the
    run's identity still matches the session's owner. No-op if unowned."""
    owner = session.metadata.get(PORT_IDENTITY_ID_KEY)
    if owner != run.execution_identity.identifier:
        raise ActionExecutionError(
            f"Cannot continue session {session.id}: owned by {owner}, "
            f"run is {run.execution_identity.identifier}"
        )

    await _upsert_vault(
        client, run.execution_identity.identifier, get_run_access_token(run), vault_name
    )
