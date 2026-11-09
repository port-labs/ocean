from __future__ import annotations

import functools
from typing import Any, cast

from anthropic.types.beta import BetaManagedAgentsAgent
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)
from anthropic.types.beta.beta_managed_agents_vault import BetaManagedAgentsVault
from anthropic.types.beta.vaults.beta_managed_agents_credential import (
    BetaManagedAgentsCredential,
)
from loguru import logger
from port_ocean.utils.async_iterators import find_first_match_in_generator

from claude_managed_agents.actions.git_auth.types import (
    AgentMcpEnsureSpec,
    McpCredentialSpec,
    normalize_mcp_server_url,
)
from claude_managed_agents.actions.port_mcp_utils import PortMcpBinding
from claude_managed_agents.clients.anthropic_client import AnthropicClient

_GITHUB_TOOLSET: dict[str, Any] = {
    "type": "mcp_toolset",
    "mcp_server_name": "github",
    "default_config": {
        "enabled": True,
        "permission_policy": {"type": "always_allow"},
    },
}


def _is_vault_credential_url_matching(
    credential: BetaManagedAgentsCredential, url: str
) -> bool:
    auth = credential.auth
    if auth.type != "static_bearer":
        return False
    return normalize_mcp_server_url(auth.mcp_server_url) == normalize_mcp_server_url(
        url
    )


def is_agent_configured_with_git_mcp(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    spec: AgentMcpEnsureSpec,
) -> bool:
    target = normalize_mcp_server_url(spec.url)
    return any(
        s.name == spec.name and normalize_mcp_server_url(s.url) == target
        for s in mcp_servers
    )


def attach_git_mcp_settings_to_agent_config(
    proposed_config: dict[str, Any],
    spec: AgentMcpEnsureSpec,
    existing_agent: BetaManagedAgentsAgent | None = None,
) -> dict[str, Any]:
    """Attach the provider MCP server + toolset to agent config."""
    agent_servers = list((existing_agent.mcp_servers or []) if existing_agent else [])
    agent_tools = list((existing_agent.tools or []) if existing_agent else [])
    proposed_servers = cast(
        list[BetaManagedAgentsMCPServerURLDefinition],
        proposed_config.get("mcp_servers") or [],
    )
    mcp_servers = _merge_mcp_servers_by_url(agent_servers + proposed_servers)
    if is_agent_configured_with_git_mcp(mcp_servers, spec):
        return proposed_config

    mcp_servers = [s for s in mcp_servers if s.name != spec.name]
    tools = [
        t
        for t in agent_tools
        if not (t.type == "mcp_toolset" and t.mcp_server_name == spec.name)
    ]
    mcp_servers.append(
        BetaManagedAgentsMCPServerURLDefinition(
            type="url", name=spec.name, url=spec.url
        )
    )
    toolset = {**_GITHUB_TOOLSET, "mcp_server_name": spec.name}
    return {
        **proposed_config,
        "mcp_servers": mcp_servers,
        "tools": [*tools, toolset],
    }


def _merge_mcp_servers_by_url(
    servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({normalize_mcp_server_url(s.url): s for s in servers}.values())


async def ensure_git_mcp_credential(
    client: AnthropicClient,
    *,
    vault_id: str | None,
    vault_name: str,
    mcp: McpCredentialSpec,
) -> PortMcpBinding:
    """Ensure a vault exists and upsert a static_bearer credential for the MCP URL.

    When ``vault_id`` is provided (e.g. from an existing Port MCP binding), that
    vault is reused. Otherwise a vault is found or created by ``vault_name``.
    """
    if vault_id is None:
        vault_match = await find_first_match_in_generator(
            client.paginate(client.beta.vaults.list()),
            lambda vault: cast(BetaManagedAgentsVault, vault).display_name == vault_name,
        )
        if vault_match is None:
            logger.info(f"Creating git MCP vault '{vault_name}'")
            raw_vault: Any = await client.beta.vaults.create(display_name=vault_name)
        else:
            raw_vault = vault_match
        vault_id = cast(BetaManagedAgentsVault, raw_vault).id

    credential_match = await find_first_match_in_generator(
        client.paginate(client.beta.vaults.credentials.list(vault_id=vault_id)),
        functools.partial(_is_vault_credential_url_matching, url=mcp.mcp_server_url),
    )
    if credential_match is None:
        logger.info(f"Creating git MCP credential '{mcp.display_name}'")
        raw_credential: Any = await client.beta.vaults.credentials.create(
            vault_id,
            auth={
                "type": "static_bearer",
                "token": mcp.token,
                "mcp_server_url": mcp.mcp_server_url,
            },
            display_name=mcp.display_name,
        )
        credential = cast(BetaManagedAgentsCredential, raw_credential)
        return PortMcpBinding(
            mcp_server_url=mcp.mcp_server_url,
            vault_id=vault_id,
            credential_id=credential.id,
        )

    credential = cast(BetaManagedAgentsCredential, credential_match)
    await client.beta.vaults.credentials.update(
        credential.id,
        vault_id=vault_id,
        auth={
            "type": "static_bearer",
            "token": mcp.token,
        },
    )
    return PortMcpBinding(
        mcp_server_url=mcp.mcp_server_url,
        vault_id=vault_id,
        credential_id=credential.id,
    )
