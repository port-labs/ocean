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


def virtual_mcp_server_url(identifier: str) -> str:
    return _normalize_port_mcp_url(
        f"{_required_port_mcp_url()}/virtual-server/{identifier}"
    )


def mcp_urls_to_ensure(
    enable_port_mcp: bool, virtual_ids: list[str] | tuple[str, ...]
) -> list[str]:
    urls = [virtual_mcp_server_url(identifier) for identifier in virtual_ids]
    if enable_port_mcp:
        urls.insert(0, _required_port_mcp_url())
    return urls


def _merge_mcp_servers_by_url(
    list1: list[BetaManagedAgentsMCPServerURLDefinition],
    list2: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({_normalize_port_mcp_url(d.url): d for d in list1 + list2}.values())


def _is_port_mcp_toolset(tool: Tool) -> bool:
    return tool.type == "mcp_toolset" and tool.mcp_server_name == PORT_MCP_SERVER_NAME


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


def _swap_stale_port_mcp_config(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    servers = [s for s in mcp_servers if s.name != PORT_MCP_SERVER_NAME]
    refreshed_tools = [t for t in tools if not _is_port_mcp_toolset(t)]
    return servers, refreshed_tools


def attach_port_mcp_settings_to_agent_config(
    proposed_config: dict[str, Any],
    existing_agent: BetaManagedAgentsAgent | None = None,
    *,
    enable_port_mcp: bool = True,
    virtual_mcp_server_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Attach Port MCP and optional virtual MCP servers + toolsets. Pass
    ``existing_agent`` on update to keep existing tools/mcp_servers."""
    agent_servers = (existing_agent.mcp_servers or []) if existing_agent else []
    agent_tools = (existing_agent.tools or []) if existing_agent else []
    proposed_servers = cast(
        list[BetaManagedAgentsMCPServerURLDefinition],
        proposed_config.get("mcp_servers") or [],
    )
    mcp_servers = _merge_mcp_servers_by_url(agent_servers, proposed_servers)
    tools = list(agent_tools)
    changed = False

    if enable_port_mcp and not is_agent_configured_with_port_mcp(mcp_servers):
        mcp_servers, tools = _swap_stale_port_mcp_config(mcp_servers, tools)
        mcp_servers.append(
            BetaManagedAgentsMCPServerURLDefinition(
                type="url", name=PORT_MCP_SERVER_NAME, url=_required_port_mcp_url()
            )
        )
        tools.append(cast(Tool, _PORT_TOOLSET))
        changed = True

    for identifier in virtual_mcp_server_ids or []:
        url = virtual_mcp_server_url(identifier)
        name = f"port-virtual-{identifier}"
        if any(_normalize_port_mcp_url(s.url) == url for s in mcp_servers):
            continue
        mcp_servers.append(
            BetaManagedAgentsMCPServerURLDefinition(type="url", name=name, url=url)
        )
        tools.append(cast(Tool, {**_PORT_TOOLSET, "mcp_server_name": name}))
        changed = True

    if not changed:
        return proposed_config
    return {**proposed_config, "mcp_servers": mcp_servers, "tools": tools}


async def ensure_port_mcp_binding(
    client: AnthropicClient,
    run: WorkflowNodeRun,
    vault_name: str,
    urls: list[str] | None = None,
) -> PortMcpBinding:
    """Find or create the user's vault, then (re)mint credentials for each URL."""
    urls = urls or [_required_port_mcp_url()]
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
    port_mcp_url = _normalize_port_mcp_url(_required_port_mcp_url())
    for url in urls:
        credential_match = await find_first_match_in_generator(
            client.paginate(client.beta.vaults.credentials.list(vault_id=vault.id)),
            functools.partial(_is_vault_credential_url_matching, url=url),
        )
        if credential_match is None:
            identifier = _normalize_port_mcp_url(url).rsplit("/", maxsplit=1)[-1]
            display_name = (
                PORT_MCP_CREDENTIAL_NAME
                if _normalize_port_mcp_url(url) == port_mcp_url
                else f"port-virtual-{identifier}"
            )
            logger.info(f"Creating Port MCP credential '{display_name}'")
            raw_credential: Any = await client.beta.vaults.credentials.create(
                vault.id,
                auth={
                    "type": "static_bearer",
                    "token": access_token,
                    "mcp_server_url": url,
                },
                display_name=display_name,
            )
            credential = cast(BetaManagedAgentsCredential, raw_credential)
        else:
            credential = credential_match
            await remint_port_mcp_credential(
                client,
                run,
                PortMcpBinding(vault_id=vault.id, credential_id=credential.id),
            )
        if first_binding is None:
            first_binding = PortMcpBinding(
                vault_id=vault.id, credential_id=credential.id
            )

    assert first_binding is not None
    return first_binding


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
