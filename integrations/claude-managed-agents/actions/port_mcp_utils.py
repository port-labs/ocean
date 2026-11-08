from __future__ import annotations

import functools
from typing import Any, cast

from anthropic.types.beta import (
    BetaManagedAgentsAgent,
)
from anthropic.types.beta.beta_managed_agents_agent import Tool
from anthropic.types.beta.beta_managed_agents_vault import BetaManagedAgentsVault
from anthropic.types.beta.vaults.beta_managed_agents_credential import (
    BetaManagedAgentsCredential,
)
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)
from loguru import logger
from pydantic import BaseModel
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.utils.async_iterators import find_first_match_in_generator
from clients.anthropic_client import AnthropicClient
from port_ocean.core.models import WorkflowNodeRun

PORT_MCP_SERVER_NAME = "port"
PORT_MCP_CREDENTIAL_NAME = "port-mcp"


class PortMcpBinding(BaseModel):
    mcp_server_url: str
    vault_id: str
    credential_id: str


def _normalize_port_mcp_url(url: str) -> str:
    # Claude matches vault credentials by exact MCP URL — keep host as-is.
    return url.rstrip("/")


def get_virtual_mcp_server_url(identifier: str) -> str:
    return _normalize_port_mcp_url(
        f"{_required_port_mcp_url()}/virtual-server/{identifier}"
    )


def port_family_mcp_urls_on_agent(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[str]:
    """Port MCP + virtual-server URLs already bound on an agent."""
    port_base = _normalize_port_mcp_url(_required_port_mcp_url())
    urls: list[str] = []
    for server in mcp_servers:
        normalized = _normalize_port_mcp_url(server.url)
        if normalized.startswith(port_base):
            urls.append(normalized)
    return urls


def _is_port_family_mcp_name(name: str) -> bool:
    return name == PORT_MCP_SERVER_NAME or name.startswith("port-virtual-mcp-")


def _merge_mcp_servers_by_url(
    list1: list[BetaManagedAgentsMCPServerURLDefinition],
    list2: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({_normalize_port_mcp_url(d.url): d for d in list1 + list2}.values())


def _is_vault_name_matching(vault: BetaManagedAgentsVault, name: str) -> bool:
    return vault.display_name == name


def _is_vault_credential_url_matching(
    credential: BetaManagedAgentsCredential, url: str
) -> bool:
    auth = credential.auth
    if auth.type != "static_bearer":
        return False
    return _normalize_port_mcp_url(auth.mcp_server_url) == _normalize_port_mcp_url(url)


def _required_port_mcp_url() -> str:
    port_mcp_url = ocean.config.port.mcp_url
    if not port_mcp_url:
        raise RuntimeError("Port MCP URL is not configured for this integration")
    return port_mcp_url


def _port_mcp_toolset(port_mcp_server_name: str) -> dict[str, Any]:
    return {
        "type": "mcp_toolset",
        "mcp_server_name": port_mcp_server_name,
        "default_config": {
            "enabled": True,
            "permission_policy": {"type": "always_allow"},
        },
    }


def _tool_mcp_server_name(tool: Tool | dict[str, Any]) -> str | None:
    if isinstance(tool, dict):
        if tool.get("type") != "mcp_toolset":
            return None
        name = tool.get("mcp_server_name")
        return name if isinstance(name, str) else None
    if tool.type != "mcp_toolset":
        return None
    return tool.mcp_server_name


def _agent_has_mcp_url(
    mcp_url: str,
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> bool:
    target = _normalize_port_mcp_url(mcp_url)
    return any(_normalize_port_mcp_url(s.url) == target for s in mcp_servers)


def _swap_stale_port_mcp_config(
    port_mcp_server_name: str,
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    servers = [s for s in mcp_servers if s.name != port_mcp_server_name]
    refreshed_tools = [
        t for t in tools if _tool_mcp_server_name(t) != port_mcp_server_name
    ]
    return servers, refreshed_tools


def _credential_display_name(url: str) -> str:
    port_mcp_url = _normalize_port_mcp_url(_required_port_mcp_url())
    normalized = _normalize_port_mcp_url(url)
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
                (name := _tool_mcp_server_name(t)) is not None
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
        if _agent_has_mcp_url(url, mcp_servers):
            continue
        changed = True
        mcp_servers, tools = _swap_stale_port_mcp_config(name, mcp_servers, tools)
        mcp_servers.append(
            BetaManagedAgentsMCPServerURLDefinition(type="url", name=name, url=url)
        )
        tools.append(cast(Tool, _port_mcp_toolset(name)))

    return {
        **proposed_config,
        "mcp_servers": mcp_servers,
        "tools": tools,
    }, changed


async def get_or_create_mcp_vault(
    client: AnthropicClient, vault_name: str
) -> BetaManagedAgentsVault:
    vault_match = cast(
        BetaManagedAgentsVault | None,
        await find_first_match_in_generator(
            client.paginate(client.beta.vaults.list()),
            functools.partial(_is_vault_name_matching, name=vault_name),
        ),
    )
    if vault_match is None:
        logger.info(f"Creating Port MCP vault '{vault_name}'")
        return await client.beta.vaults.create(display_name=vault_name)

    return vault_match


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

    url = _normalize_port_mcp_url(mcp_server_url)
    credential_match = await find_first_match_in_generator(
        client.paginate(client.beta.vaults.credentials.list(vault_id=vault_id)),
        functools.partial(_is_vault_credential_url_matching, url=url),
    )
    display_name = _credential_display_name(url)
    if credential_match is None:
        logger.info(f"Creating Port MCP credential '{display_name}'")
        raw_credential: Any = await client.beta.vaults.credentials.create(
            vault_id,
            auth={
                "type": "static_bearer",
                "token": access_token,
                "mcp_server_url": url,
            },
            display_name=display_name,
        )
        credential = cast(BetaManagedAgentsCredential, raw_credential)
    else:
        credential = cast(BetaManagedAgentsCredential, credential_match)
        binding = PortMcpBinding(
            mcp_server_url=url,
            vault_id=vault_id,
            credential_id=credential.id,
        )
        await remint_port_mcp_credential(client, run, binding)
    return PortMcpBinding(
        mcp_server_url=url,
        vault_id=vault_id,
        credential_id=credential.id,
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
    await client.beta.vaults.credentials.update(
        binding.credential_id,
        vault_id=binding.vault_id,
        auth={
            "type": "static_bearer",
            "token": access_token,
        },
    )
