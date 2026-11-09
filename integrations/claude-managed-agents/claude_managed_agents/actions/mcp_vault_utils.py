"""Shared Anthropic vault + MCP server helpers used by Port and git MCP bindings."""

from __future__ import annotations

import functools
from typing import Any, cast

from anthropic.types.beta.beta_managed_agents_agent import Tool
from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
    BetaManagedAgentsMCPServerURLDefinition,
)
from anthropic.types.beta.beta_managed_agents_vault import BetaManagedAgentsVault
from anthropic.types.beta.vaults.beta_managed_agents_credential import (
    BetaManagedAgentsCredential,
)
from loguru import logger
from port_ocean.utils.async_iterators import find_first_match_in_generator
from pydantic import BaseModel

from claude_managed_agents.clients.anthropic_client import AnthropicClient


class McpVaultBinding(BaseModel):
    mcp_server_url: str
    vault_id: str
    credential_id: str


def normalize_mcp_server_url(url: str) -> str:
    # Claude matches vault credentials by exact MCP URL — keep host as-is.
    return url.rstrip("/")


def is_vault_name_matching(vault: BetaManagedAgentsVault, name: str) -> bool:
    return vault.display_name == name


def is_vault_credential_url_matching(
    credential: BetaManagedAgentsCredential, url: str
) -> bool:
    auth = credential.auth
    if auth.type != "static_bearer":
        return False
    return normalize_mcp_server_url(auth.mcp_server_url) == normalize_mcp_server_url(
        url
    )


def mcp_toolset(server_name: str) -> dict[str, Any]:
    return {
        "type": "mcp_toolset",
        "mcp_server_name": server_name,
        "default_config": {
            "enabled": True,
            "permission_policy": {"type": "always_allow"},
        },
    }


def tool_mcp_server_name(tool: Tool | dict[str, Any]) -> str | None:
    if isinstance(tool, dict):
        if tool.get("type") != "mcp_toolset":
            return None
        name = tool.get("mcp_server_name")
        return name if isinstance(name, str) else None
    if tool.type != "mcp_toolset":
        return None
    return tool.mcp_server_name


def agent_has_mcp_url(
    mcp_url: str,
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
) -> bool:
    target = normalize_mcp_server_url(mcp_url)
    return any(normalize_mcp_server_url(s.url) == target for s in mcp_servers)


def agent_has_mcp_server(
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    *,
    name: str,
    url: str,
) -> bool:
    target = normalize_mcp_server_url(url)
    return any(
        s.name == name and normalize_mcp_server_url(s.url) == target
        for s in mcp_servers
    )


def swap_stale_mcp_config(
    server_name: str,
    mcp_servers: list[BetaManagedAgentsMCPServerURLDefinition],
    tools: list[Tool],
) -> tuple[list[BetaManagedAgentsMCPServerURLDefinition], list[Tool]]:
    servers = [s for s in mcp_servers if s.name != server_name]
    refreshed_tools = [t for t in tools if tool_mcp_server_name(t) != server_name]
    return servers, refreshed_tools


async def get_or_create_mcp_vault(
    client: AnthropicClient, vault_name: str
) -> BetaManagedAgentsVault:
    vault_match = cast(
        BetaManagedAgentsVault | None,
        await find_first_match_in_generator(
            client.paginate(client.beta.vaults.list()),
            functools.partial(is_vault_name_matching, name=vault_name),
        ),
    )
    if vault_match is None:
        logger.info(f"Creating MCP vault '{vault_name}'")
        return await client.beta.vaults.create(display_name=vault_name)

    return vault_match


async def ensure_static_bearer_credential(
    client: AnthropicClient,
    vault_id: str,
    *,
    mcp_server_url: str,
    token: str,
    display_name: str,
) -> McpVaultBinding:
    """Create or refresh a static_bearer vault credential for one MCP URL."""
    url = normalize_mcp_server_url(mcp_server_url)
    credential_match = await find_first_match_in_generator(
        client.paginate(client.beta.vaults.credentials.list(vault_id=vault_id)),
        functools.partial(is_vault_credential_url_matching, url=url),
    )
    if credential_match is None:
        logger.info(f"Creating MCP credential '{display_name}'")
        raw_credential: Any = await client.beta.vaults.credentials.create(
            vault_id,
            auth={
                "type": "static_bearer",
                "token": token,
                "mcp_server_url": url,
            },
            display_name=display_name,
        )
        credential = cast(BetaManagedAgentsCredential, raw_credential)
    else:
        credential = cast(BetaManagedAgentsCredential, credential_match)
        await update_static_bearer_token(
            client,
            vault_id=vault_id,
            credential_id=credential.id,
            token=token,
        )
    return McpVaultBinding(
        mcp_server_url=url,
        vault_id=vault_id,
        credential_id=credential.id,
    )


async def update_static_bearer_token(
    client: AnthropicClient,
    *,
    vault_id: str,
    credential_id: str,
    token: str,
) -> None:
    await client.beta.vaults.credentials.update(
        credential_id,
        vault_id=vault_id,
        auth={
            "type": "static_bearer",
            "token": token,
        },
    )
