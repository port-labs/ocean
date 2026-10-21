from __future__ import annotations

import functools
from typing import Any, cast

from anthropic.types.beta import (
    BetaManagedAgentsAgent,
)
from anthropic.types.beta.beta_managed_agents_vault import BetaManagedAgentsVault
from anthropic.types.beta.vaults.beta_managed_agents_credential import (
    BetaManagedAgentsCredential,
)
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)
from anthropic.types.beta.beta_managed_agents_mcp_toolset import (
    BetaManagedAgentsMCPToolset,
    BetaManagedAgentsMCPToolsetDefaultConfig,
)
from loguru import logger
from pydantic import BaseModel
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import (
    get_run_access_token,
    resolve_port_mcp_url,
)
from utils.misc import find_first_item_in_generator
from clients.anthropic_client import AnthropicClient
from port_ocean.core.models import WorkflowNodeRun

PORT_MCP_SERVER_NAME = "port"
PORT_MCP_CREDENTIAL_NAME = "port-mcp"
_PORT_TOOLSET = BetaManagedAgentsMCPToolset(
    type="mcp_toolset",
    mcp_server_name=PORT_MCP_SERVER_NAME,
    default_config=BetaManagedAgentsMCPToolsetDefaultConfig(
        permission_policy={"type": "always_allow"}
    ),
)


class PortMcpBinding(BaseModel):
    vault_id: str
    credential_id: str


def _normalize_port_mcp_url(url: str) -> str:
    return url.replace("getport", "port").rstrip("/")


def _merge_mcp_servers_by_url(
    list1: list[BetaManagedAgentsMCPServerURLDefinition],
    list2: list[BetaManagedAgentsMCPServerURLDefinition],
) -> list[BetaManagedAgentsMCPServerURLDefinition]:
    return list({_normalize_port_mcp_url(d.url): d for d in list1 + list2}.values())


def _build_port_mcp_auth(run: WorkflowNodeRun) -> dict[str, Any]:
    return {
        "type": "static_bearer",
        "token": get_run_access_token(run),
        "mcp_server_url": resolve_port_mcp_url(ocean.config.port.base_url),
    }


def is_vault_name_matching(vault: BetaManagedAgentsVault, name: str) -> bool:
    return vault.display_name == name


def is_vault_credential_name_matching(
    credential: BetaManagedAgentsCredential, name: str
) -> bool:
    return credential.display_name == name


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


async def ensure_port_mcp_binding(
    client: AnthropicClient, run: WorkflowNodeRun, vault_name: str
) -> PortMcpBinding:
    """Find or create the user's vault, then (re)mint its Port MCP credential."""
    vault = await find_first_item_in_generator(
        client.paginate(client.beta.vaults.list()),
        functools.partial(is_vault_name_matching, name=vault_name),
    )
    if vault is None:
        logger.info(f"Creating Port MCP vault '{vault_name}'")
        vault = await client.beta.vaults.create(display_name=vault_name)

    credential = await find_first_item_in_generator(
        client.paginate(client.beta.vaults.credentials.list(vault_id=vault.id)),
        functools.partial(
            is_vault_credential_name_matching, name=PORT_MCP_CREDENTIAL_NAME
        ),
    )
    if credential is None:
        logger.info(f"Creating Port MCP credential '{PORT_MCP_CREDENTIAL_NAME}'")
        credential = await client.beta.vaults.credentials.create(
            vault.id,
            auth=_build_port_mcp_auth(run),
            display_name=PORT_MCP_CREDENTIAL_NAME,
        )
    else:
        await remint_port_mcp_credential(
            client, run, PortMcpBinding(vault_id=vault.id, credential_id=credential.id)
        )
    return PortMcpBinding(vault_id=vault.id, credential_id=credential.id)


async def remint_port_mcp_credential(
    client: AnthropicClient, run: WorkflowNodeRun, binding: PortMcpBinding
) -> None:
    """Remint the vault credential for a continued session, verifying the
    run's identity still matches the session's owner. No-op if unowned."""
    await client.beta.vaults.credentials.update(
        binding.credential_id, vault_id=binding.vault_id, auth=_build_port_mcp_auth(run)
    )
