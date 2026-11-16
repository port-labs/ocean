from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from azure_integration.foundry.helpers.utils import deep_merge

PORT_MCP_SERVER_LABEL = "port"

# ponytail: Foundry stores MCP auth on the agent (project-scoped headers). Concurrent
# SA/actor runs that remint the same agent overwrite each other's Bearer token.


def required_port_mcp_url() -> str:
    port_mcp_url = ocean.config.port.mcp_url
    if not port_mcp_url:
        raise RuntimeError("Port MCP URL is not configured for this integration")
    return str(port_mcp_url).rstrip("/")


def port_mcp_tool(*, access_token: str | None = None) -> dict[str, Any]:
    tool: dict[str, Any] = {
        "type": "mcp",
        "server_label": PORT_MCP_SERVER_LABEL,
        "server_url": required_port_mcp_url(),
        "require_approval": "never",
    }
    if access_token:
        tool["headers"] = {"Authorization": f"Bearer {access_token}"}
    return tool


def _is_port_mcp_tool(tool: Any) -> bool:
    return (
        isinstance(tool, dict)
        and tool.get("type") == "mcp"
        and tool.get("server_label") == PORT_MCP_SERVER_LABEL
    )


def merge_port_mcp_into_tools(
    tools: list[Any],
    *,
    enable_port_mcp: bool,
    access_token: str | None,
) -> list[Any]:
    others = [tool for tool in tools if not _is_port_mcp_tool(tool)]
    if not enable_port_mcp:
        return others
    return [*others, port_mcp_tool(access_token=access_token)]


def attach_port_mcp_to_agent_config(
    config: dict[str, Any],
    *,
    enable_port_mcp: bool,
    access_token: str | None,
    existing_tools: list[Any] | None = None,
) -> dict[str, Any]:
    """Ensure or remove the Port MCP tool under ``definition.tools``."""
    merged = deep_merge(
        {"definition": {"tools": list(existing_tools or [])}},
        config,
    )
    definition = merged.get("definition")
    if not isinstance(definition, dict):
        definition = {}
        merged["definition"] = definition
    tools = definition.get("tools")
    if not isinstance(tools, list):
        tools = []
    definition["tools"] = merge_port_mcp_into_tools(
        tools,
        enable_port_mcp=enable_port_mcp,
        access_token=access_token,
    )
    return merged


def tools_from_agent_payload(agent: Any) -> list[Any]:
    if not isinstance(agent, dict):
        return []
    definition = agent.get("definition")
    if not isinstance(definition, dict):
        return []
    tools = definition.get("tools")
    return tools if isinstance(tools, list) else []


async def fetch_agent_tools(
    client: Any, *, project_endpoint: str, agent_id: str
) -> list[Any]:
    try:
        agent = await client.send_api_request(
            client.build_url(project_endpoint, f"agents/{agent_id}")
        )
    except Exception as error:
        logger.warning(
            f"Could not load agent {agent_id} tools for Port MCP merge: {error}"
        )
        return []
    return tools_from_agent_payload(agent)


async def remint_port_mcp_on_agent(
    client: Any,
    *,
    project_endpoint: str,
    agent_id: str,
    access_token: str,
) -> None:
    """Refresh Port MCP Bearer headers on an existing agent (project-scoped)."""
    existing = await fetch_agent_tools(
        client, project_endpoint=project_endpoint, agent_id=agent_id
    )
    config = attach_port_mcp_to_agent_config(
        {},
        enable_port_mcp=True,
        access_token=access_token,
        existing_tools=existing,
    )
    try:
        await client.send_api_request(
            client.build_url(project_endpoint, f"agents/{agent_id}"),
            method="PATCH",
            json_body={"definition": {"tools": config["definition"]["tools"]}},
        )
    except Exception as error:
        logger.warning(f"Failed to remint Port MCP on agent {agent_id}: {error}")
