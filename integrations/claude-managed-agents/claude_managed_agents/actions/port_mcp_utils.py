from __future__ import annotations

from typing import Any, cast

from anthropic.types.beta import (
    BetaManagedAgentsAgent,
)
from anthropic.types.beta.beta_managed_agents_agent import Tool
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import WorkflowNodeRun

from claude_managed_agents.actions.mcp_vault_utils import (
    McpVaultBinding,
    agent_has_mcp_url,
    ensure_static_bearer_credential,
    get_or_create_mcp_vault,
    mcp_toolset,
    normalize_mcp_server_url,
    swap_stale_mcp_config,
    tool_mcp_server_name,
    update_static_bearer_token,
)
from claude_managed_agents.clients.anthropic_client import AnthropicClient

PORT_MCP_SERVER_NAME = "port"
PORT_MCP_CREDENTIAL_NAME = "port-mcp"

# Kept for call-site compatibility; prefer McpVaultBinding for new code.
PortMcpBinding = McpVaultBinding


def get_virtual_mcp_server_url(identifier: str) -> str:
    return normalize_mcp_server_url(
        f"{_required_port_mcp_url()}/virtual-server/{identifier}"
    )


def port_family_mcp_urls_on_agent(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[str]:
    """Port MCP + virtual-server URLs already bound on an agent."""
    port_base = normalize_mcp_server_url(_required_port_mcp_url())
    urls: list[str] = []
    for server in mcp_servers:
        normalized = normalize_mcp_server_url(server.url)
        if normalized.startswith(port_base):
            urls.append(normalized)
    return urls


def _is_port_family_mcp_name(name: str) -> bool:
    return name == PORT_MCP_SERVER_NAME or name.startswith("port-virtual-mcp-")


def _merge_mcp_servers_by_url(
    list1: list[BetaManagedAgentsMCPServerURLDefinition],
    list2: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({normalize_mcp_server_url(d.url): d for d in list1 + list2}.values())


def _required_port_mcp_url() -> str:
    port_mcp_url = ocean.config.port.mcp_url
    if not port_mcp_url:
        raise RuntimeError("Port MCP URL is not configured for this integration")
    return port_mcp_url


def _credential_display_name(url: str) -> str:
    port_mcp_url = normalize_mcp_server_url(_required_port_mcp_url())
    normalized = normalize_mcp_server_url(url)
    if normalized == port_mcp_url:
        return PORT_MCP_CREDENTIAL_NAME
    return f"port-virtual-{normalized.rsplit('/', maxsplit=1)[-1]}"


def attach_port_mcp_settings_to_agent_config(
    proposed_config: dict[str, Any],
    existing_agent: BetaManagedAgentsAgent | None = None,
    *,
    enable_port_mcp: bool,
    virtual_mcp_server_ids: list[str],
    replace: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Attach Port MCP and optional virtual MCP servers + toolsets.

    ``replace=False`` (trigger): ensure/merge onto the existing agent.
    ``replace=True`` (update): drop existing Port/virtual MCP bindings first,
    then set exactly ``enable_port_mcp`` + ``virtual_mcp_server_ids``.
    Non-Port MCP servers/tools are always kept.
    """
    agent_servers = (existing_agent.mcp_servers or []) if existing_agent else []
    agent_tools = (existing_agent.tools or []) if existing_agent else []
    proposed_servers = cast(
        list[BetaManagedAgentsMCPServerURLDefinition],
        proposed_config.get("mcp_servers") or [],
    )
    if replace:
        agent_servers = [
            s for s in agent_servers if not _is_port_family_mcp_name(s.name)
        ]
        agent_tools = [
            t
            for t in agent_tools
            if not (
                (name := tool_mcp_server_name(t)) is not None
                and _is_port_family_mcp_name(name)
            )
        ]
        proposed_servers = [
            s for s in proposed_servers if not _is_port_family_mcp_name(s.name)
        ]

    mcp_servers = _merge_mcp_servers_by_url(agent_servers, proposed_servers)
    tools = list(agent_tools)
    changed = replace

    targets: list[tuple[str, str]] = []
    if enable_port_mcp:
        targets.append((_required_port_mcp_url(), PORT_MCP_SERVER_NAME))
    for identifier in virtual_mcp_server_ids:
        targets.append(
            (get_virtual_mcp_server_url(identifier), f"port-virtual-mcp-{identifier}")
        )

    for url, name in targets:
        if agent_has_mcp_url(url, mcp_servers):
            continue
        changed = True
        mcp_servers, tools = swap_stale_mcp_config(name, mcp_servers, tools)
        mcp_servers.append(
            BetaManagedAgentsMCPServerURLDefinition(type="url", name=name, url=url)
        )
        tools.append(cast(Tool, mcp_toolset(name)))

    return {
        **proposed_config,
        "mcp_servers": mcp_servers,
        "tools": tools,
    }, changed


async def ensure_port_mcp_credential(
    client: AnthropicClient,
    run: WorkflowNodeRun,
    vault_id: str,
    mcp_server_url: str,
) -> PortMcpBinding:
    """Create or remint the vault credential for one MCP URL."""
    access_token = get_run_access_token(run)
    if access_token is None:
        raise RuntimeError(
            "portAccessToken is required to mint Port-family MCP vault credentials"
        )

    return await ensure_static_bearer_credential(
        client,
        vault_id,
        mcp_server_url=mcp_server_url,
        token=access_token,
        display_name=_credential_display_name(mcp_server_url),
    )


def port_mcp_binding_cache_key(vault_name: str, mcp_server_url: str) -> str:
    # Vault name scopes the cache per user vault; the same MCP URL is stored on many vaults.
    return f"{vault_name}:{mcp_server_url}"


async def remint_port_mcp_credential(
    client: AnthropicClient, run: WorkflowNodeRun, binding: PortMcpBinding
) -> None:
    """Refresh the vault bearer token from the workflow run's portAccessToken."""
    access_token = get_run_access_token(run)
    if access_token is None:
        raise RuntimeError(
            "portAccessToken is required to remint Port-family MCP vault credentials"
        )
    await update_static_bearer_token(
        client,
        vault_id=binding.vault_id,
        credential_id=binding.credential_id,
        token=access_token,
    )
