from __future__ import annotations

from typing import Any

from anthropic.types.beta import BetaManagedAgentsAgent
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)

from claude_managed_agents.actions.git_auth.types import (
    AgentMcpEnsureSpec,
    McpCredentialSpec,
)
from claude_managed_agents.actions.mcp_vault_utils import (
    McpVaultBinding,
    agent_has_mcp_server,
    ensure_static_bearer_credential,
    get_or_create_mcp_vault,
    mcp_toolset,
    swap_stale_mcp_config,
)
from claude_managed_agents.clients.anthropic_client import AnthropicClient


def is_agent_configured_with_git_mcp(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    spec: AgentMcpEnsureSpec,
) -> bool:
    return agent_has_mcp_server(mcp_servers, name=spec.name, url=spec.url)


def attach_git_mcp_settings_to_agent_config(
    spec: AgentMcpEnsureSpec,
    agent: BetaManagedAgentsAgent,
) -> dict[str, Any]:
    """Build an update payload that attaches the provider MCP server + toolset."""
    mcp_servers, tools = swap_stale_mcp_config(
        spec.name,
        list(agent.mcp_servers or []),
        list(agent.tools or []),
    )
    mcp_servers.append(
        BetaManagedAgentsMCPServerURLDefinition(
            type="url", name=spec.name, url=spec.url
        )
    )
    return {
        "mcp_servers": mcp_servers,
        "tools": [*tools, mcp_toolset(spec.name)],
    }


async def ensure_git_mcp_credential(
    client: AnthropicClient,
    *,
    vault_id: str | None,
    vault_name: str,
    mcp: McpCredentialSpec,
) -> McpVaultBinding:
    """Ensure a vault exists and upsert a static_bearer credential for the MCP URL.

    When ``vault_id`` is provided (e.g. from an existing Port MCP binding), that
    vault is reused. Otherwise a vault is found or created by ``vault_name``.
    """
    if vault_id is None:
        vault_id = (await get_or_create_mcp_vault(client, vault_name)).id

    return await ensure_static_bearer_credential(
        client,
        vault_id,
        mcp_server_url=mcp.mcp_server_url,
        token=mcp.token,
        display_name=mcp.display_name,
    )
