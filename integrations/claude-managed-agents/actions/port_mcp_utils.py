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
VIRTUAL_MCP_SERVER_NAME_PREFIX = "port-virtual-"
VIRTUAL_MCP_CREDENTIAL_PREFIX = "port-virtual-"
_PORT_TOOLSET: dict[str, Any] = {
    "type": "mcp_toolset",
    "mcp_server_name": PORT_MCP_SERVER_NAME,
    "default_config": {
        "enabled": True,
        "permission_policy": {"type": "always_allow"},
    },
}


class PortMcpBinding(BaseModel):
    vault_id: str
    credential_id: str


def _normalize_port_mcp_url(url: str) -> str:
    # Claude matches vault credentials by exact MCP URL — keep host as-is.
    return url.rstrip("/")


def virtual_mcp_server_name(identifier: str) -> str:
    return f"{VIRTUAL_MCP_SERVER_NAME_PREFIX}{identifier}"


def virtual_mcp_server_url(identifier: str) -> str:
    base = _required_port_mcp_url()
    return _normalize_port_mcp_url(f"{base}/virtual-server/{identifier}")


def virtual_mcp_credential_name(identifier: str) -> str:
    return f"{VIRTUAL_MCP_CREDENTIAL_PREFIX}{identifier}"


def _virtual_mcp_toolset(server_name: str) -> dict[str, Any]:
    return {
        "type": "mcp_toolset",
        "mcp_server_name": server_name,
        "default_config": {
            "enabled": True,
            "permission_policy": {"type": "always_allow"},
        },
    }


def _merge_mcp_servers_by_url(
    list1: list[BetaManagedAgentsMCPServerURLDefinition],
    list2: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({_normalize_port_mcp_url(d.url): d for d in list1 + list2}.values())


def _is_port_mcp_toolset(tool: Tool) -> bool:
    return tool.type == "mcp_toolset" and tool.mcp_server_name == PORT_MCP_SERVER_NAME


def _is_managed_virtual_mcp_server_name(name: str) -> bool:
    return name.startswith(VIRTUAL_MCP_SERVER_NAME_PREFIX)


def _is_managed_virtual_mcp_toolset(tool: Tool) -> bool:
    if tool.type != "mcp_toolset":
        return False
    return _is_managed_virtual_mcp_server_name(tool.mcp_server_name)


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


def is_agent_configured_with_port_mcp(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> bool:
    port_mcp_url = ocean.config.port.mcp_url
    return port_mcp_url is not None and any(
        _normalize_port_mcp_url(s.url) == _normalize_port_mcp_url(port_mcp_url)
        for s in mcp_servers
    )


def is_agent_configured_with_virtual_mcp(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    virtual_mcp_server_ids: list[str],
) -> bool:
    if not virtual_mcp_server_ids:
        return True
    urls = {virtual_mcp_server_url(identifier) for identifier in virtual_mcp_server_ids}
    configured = {_normalize_port_mcp_url(s.url) for s in mcp_servers}
    return urls.issubset(configured)


def collect_managed_mcp_urls(
    *,
    enable_port_mcp: bool,
    virtual_mcp_server_ids: list[str],
) -> list[str]:
    urls: list[str] = []
    if enable_port_mcp:
        urls.append(_required_port_mcp_url())
    for identifier in virtual_mcp_server_ids:
        urls.append(virtual_mcp_server_url(identifier))
    return urls


def _credential_display_name_for_url(url: str) -> str:
    port_mcp_url = _normalize_port_mcp_url(_required_port_mcp_url())
    normalized = _normalize_port_mcp_url(url)
    if normalized == port_mcp_url:
        return PORT_MCP_CREDENTIAL_NAME
    prefix = f"{port_mcp_url}/virtual-server/"
    if normalized.startswith(prefix):
        identifier = normalized.removeprefix(prefix)
        return virtual_mcp_credential_name(identifier)
    return f"port-mcp-{normalized.rsplit('/', maxsplit=1)[-1]}"


def _swap_stale_port_mcp_config(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    servers = [s for s in mcp_servers if s.name != PORT_MCP_SERVER_NAME]
    refreshed_tools = [t for t in tools if not _is_port_mcp_toolset(t)]
    return servers, refreshed_tools


def _remove_managed_port_mcp_config(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    servers = [s for s in mcp_servers if s.name != PORT_MCP_SERVER_NAME]
    refreshed_tools = [t for t in tools if not _is_port_mcp_toolset(t)]
    return servers, refreshed_tools


def _remove_managed_virtual_mcp_servers(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
    *,
    keep_identifiers: set[str],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    keep_names = {virtual_mcp_server_name(identifier) for identifier in keep_identifiers}
    servers = [
        server
        for server in mcp_servers
        if not _is_managed_virtual_mcp_server_name(server.name)
        or server.name in keep_names
    ]
    refreshed_tools = [
        tool
        for tool in tools
        if not _is_managed_virtual_mcp_toolset(tool)
        or tool.mcp_server_name in keep_names
    ]
    return servers, refreshed_tools


def _attach_virtual_mcp_servers(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
    virtual_mcp_server_ids: list[str],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    updated_servers = list(mcp_servers)
    updated_tools = list(tools)
    configured_urls = {_normalize_port_mcp_url(s.url) for s in updated_servers}
    configured_toolsets = {
        t.mcp_server_name for t in updated_tools if t.type == "mcp_toolset"
    }
    for identifier in virtual_mcp_server_ids:
        url = virtual_mcp_server_url(identifier)
        server_name = virtual_mcp_server_name(identifier)
        if _normalize_port_mcp_url(url) not in configured_urls:
            updated_servers.append(
                BetaManagedAgentsMCPServerURLDefinition(
                    type="url", name=server_name, url=url
                )
            )
            configured_urls.add(_normalize_port_mcp_url(url))
        if server_name not in configured_toolsets:
            updated_tools.append(cast(Tool, _virtual_mcp_toolset(server_name)))
            configured_toolsets.add(server_name)
    return updated_servers, updated_tools


def attach_port_mcp_settings_to_agent_config(
    proposed_config: dict[str, Any],
    existing_agent: BetaManagedAgentsAgent | None = None,
    *,
    enable_port_mcp: bool = True,
    virtual_mcp_server_ids: list[str] | None = None,
    remove_port_mcp: bool = False,
    reconcile_virtual_mcp_server_ids: bool = False,
) -> dict[str, Any]:
    """Attach managed Port / virtual MCP servers and toolsets to agent config."""
    virtual_ids = list(virtual_mcp_server_ids or [])
    agent_servers = (existing_agent.mcp_servers or []) if existing_agent else []
    agent_tools = (existing_agent.tools or []) if existing_agent else []
    proposed_servers = cast(
        list[BetaManagedAgentsMCPServerURLDefinition],
        proposed_config.get("mcp_servers") or [],
    )
    proposed_tools = cast(list[Tool], proposed_config.get("tools") or [])
    mcp_servers = _merge_mcp_servers_by_url(agent_servers, proposed_servers)
    tools = list(agent_tools) if existing_agent else list(proposed_tools)

    if remove_port_mcp:
        mcp_servers, tools = _remove_managed_port_mcp_config(mcp_servers, tools)

    if reconcile_virtual_mcp_server_ids:
        mcp_servers, tools = _remove_managed_virtual_mcp_servers(
            mcp_servers, tools, keep_identifiers=set(virtual_ids)
        )

    if virtual_ids:
        mcp_servers, tools = _attach_virtual_mcp_servers(mcp_servers, tools, virtual_ids)

    if enable_port_mcp:
        port_mcp_url = _required_port_mcp_url()
        if not is_agent_configured_with_port_mcp(mcp_servers):
            mcp_servers, tools = _swap_stale_port_mcp_config(mcp_servers, tools)
            mcp_servers.append(
                BetaManagedAgentsMCPServerURLDefinition(
                    type="url", name=PORT_MCP_SERVER_NAME, url=port_mcp_url
                )
            )
            tools.append(cast(Tool, _PORT_TOOLSET))

    mcp_requested = (
        enable_port_mcp
        or bool(virtual_ids)
        or remove_port_mcp
        or reconcile_virtual_mcp_server_ids
    )
    if not mcp_requested:
        return proposed_config

    return {
        **proposed_config,
        "mcp_servers": mcp_servers,
        "tools": tools,
    }


def agent_needs_managed_mcp_update(
    agent: BetaManagedAgentsAgent,
    *,
    enable_port_mcp: bool,
    virtual_mcp_server_ids: list[str],
) -> bool:
    servers = agent.mcp_servers or []
    if enable_port_mcp and not is_agent_configured_with_port_mcp(servers):
        return True
    if virtual_mcp_server_ids and not is_agent_configured_with_virtual_mcp(
        servers, virtual_mcp_server_ids
    ):
        return True
    return False


async def ensure_port_mcp_binding(
    client: AnthropicClient, run: WorkflowNodeRun, vault_name: str
) -> PortMcpBinding:
    """Find or create the user's vault, then (re)mint its Port MCP credential."""
    binding = await ensure_mcp_bindings(
        client,
        run,
        vault_name,
        collect_managed_mcp_urls(
            enable_port_mcp=True, virtual_mcp_server_ids=[]
        ),
    )
    return binding


async def ensure_mcp_bindings(
    client: AnthropicClient,
    run: WorkflowNodeRun,
    vault_name: str,
    mcp_urls: list[str],
) -> PortMcpBinding:
    """Find or create a vault, then create or remint bearer credentials for each URL."""
    if not mcp_urls:
        raise ValueError("At least one MCP URL is required to ensure bindings")

    vault_match = await find_first_match_in_generator(
        client.paginate(client.beta.vaults.list()),
        functools.partial(_is_vault_name_matching, name=vault_name),
    )
    raw_vault: Any
    if vault_match is None:
        logger.info(f"Creating Port MCP vault '{vault_name}'")
        raw_vault = await client.beta.vaults.create(display_name=vault_name)
    else:
        raw_vault = vault_match
    vault = cast(BetaManagedAgentsVault, raw_vault)

    access_token = get_run_access_token(run)
    if access_token is None:
        raise RuntimeError("portAccessToken is required when executionIdentity is set")

    first_binding: PortMcpBinding | None = None
    for url in mcp_urls:
        credential_name = _credential_display_name_for_url(url)
        credential_match = await find_first_match_in_generator(
            client.paginate(client.beta.vaults.credentials.list(vault_id=vault.id)),
            functools.partial(_is_vault_credential_url_matching, url=url),
        )
        if credential_match is None:
            logger.info(f"Creating MCP credential '{credential_name}' for {url}")
            raw_credential: Any = await client.beta.vaults.credentials.create(
                vault.id,
                auth={
                    "type": "static_bearer",
                    "token": access_token,
                    "mcp_server_url": url,
                },
                display_name=credential_name,
            )
            credential = cast(BetaManagedAgentsCredential, raw_credential)
        else:
            credential = cast(BetaManagedAgentsCredential, credential_match)
            await remint_port_mcp_credential(
                client,
                run,
                PortMcpBinding(vault_id=vault.id, credential_id=credential.id),
            )
        binding = PortMcpBinding(vault_id=vault.id, credential_id=credential.id)
        if first_binding is None:
            first_binding = binding

    assert first_binding is not None
    return first_binding


async def remint_managed_mcp_credentials(
    client: AnthropicClient,
    run: WorkflowNodeRun,
    vault_id: str,
    mcp_urls: list[str],
) -> None:
    for url in mcp_urls:
        credential_match = await find_first_match_in_generator(
            client.paginate(client.beta.vaults.credentials.list(vault_id=vault_id)),
            functools.partial(_is_vault_credential_url_matching, url=url),
        )
        if credential_match is None:
            continue
        await remint_port_mcp_credential(
            client,
            run,
            PortMcpBinding(vault_id=vault_id, credential_id=credential_match.id),
        )


async def remint_port_mcp_credential(
    client: AnthropicClient, run: WorkflowNodeRun, binding: PortMcpBinding
) -> None:
    """Remint the vault credential for a continued session, verifying the
    run's identity still matches the session's owner. No-op if unowned."""
    access_token = get_run_access_token(run)
    if access_token is None:
        raise RuntimeError("portAccessToken is required when executionIdentity is set")
    await client.beta.vaults.credentials.update(
        binding.credential_id,
        vault_id=binding.vault_id,
        auth={
            "type": "static_bearer",
            "token": access_token,
        },
    )
