from __future__ import annotations

import hashlib
import re
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.clients.project_connections_client import ProjectConnectionsClient
from azure_integration.foundry.helpers.project_scope import get_project_endpoint, project_name_from_endpoint

PORT_MCP_SERVER_LABEL = "port"
_PLACEHOLDER_BEARER = "Bearer port-ocean-placeholder"


def required_port_mcp_url() -> str:
    port_mcp_url = ocean.config.port.mcp_url
    if not port_mcp_url:
        raise RuntimeError("Port MCP URL is not configured for this integration")
    return port_mcp_url.rstrip("/")


def port_mcp_connection_name(agent_id: str) -> str:
    """ARM connection name: ^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$"""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", agent_id).strip("-_")
    name = f"port-{slug}" if slug else "port-mcp"
    if len(name) < 3:
        digest = hashlib.sha256(agent_id.encode()).hexdigest()[:28]
        name = f"port-{digest}"
    return name[:33]


def _port_mcp_tool(connection_name: str, server_url: str) -> dict[str, Any]:
    return {
        "type": "mcp",
        "server_label": PORT_MCP_SERVER_LABEL,
        "server_url": server_url,
        "project_connection_id": connection_name,
        "require_approval": "never",
    }


def _definition_has_port_mcp(
    definition: dict[str, Any], *, connection_name: str, server_url: str
) -> bool:
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return False
    normalized_url = server_url.rstrip("/")
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "mcp":
            continue
        conn = tool.get("project_connection_id")
        url = str(tool.get("server_url") or "").rstrip("/")
        if conn == connection_name and url == normalized_url:
            return True
    return False


def _latest_definition(agent: dict[str, Any]) -> dict[str, Any]:
    versions = agent.get("versions")
    if isinstance(versions, dict):
        latest = versions.get("latest")
        if isinstance(latest, dict):
            definition = latest.get("definition")
            if isinstance(definition, dict):
                return dict(definition)
    definition = agent.get("definition")
    if isinstance(definition, dict):
        return dict(definition)
    return {"kind": "prompt"}


async def ensure_port_mcp_on_agent(
    foundry: FoundryHttpClient,
    connections: ProjectConnectionsClient,
    *,
    agent_id: str,
    run: IntegrationRun,
) -> str:
    """Ensure project connection + agent definition include Port MCP. Returns connection name."""
    server_url = required_port_mcp_url()
    connection_name = port_mcp_connection_name(agent_id)
    project_name = project_name_from_endpoint(get_project_endpoint())

    await connections.upsert_bearer_connection(
        project_name=project_name,
        connection_name=connection_name,
        target_url=server_url,
        bearer_token=_PLACEHOLDER_BEARER,
    )

    project_endpoint = get_project_endpoint()
    agent_payload = await foundry.send_api_request(
        foundry.build_url(project_endpoint, f"agents/{agent_id}"),
    )
    if not isinstance(agent_payload, dict) or not agent_payload:
        raise ActionExecutionError(f"Could not load Foundry agent {agent_id}")

    definition = _latest_definition(agent_payload)
    if _definition_has_port_mcp(
        definition, connection_name=connection_name, server_url=server_url
    ):
        return connection_name

    tools = list(definition.get("tools") or [])
    tools = [
        t
        for t in tools
        if not (
            isinstance(t, dict)
            and t.get("type") == "mcp"
            and t.get("server_label") == PORT_MCP_SERVER_LABEL
        )
    ]
    tools.append(_port_mcp_tool(connection_name, server_url))
    new_definition = {**definition, "tools": tools}

    await foundry.send_api_request(
        foundry.build_url(project_endpoint, f"agents/{agent_id}/versions"),
        method="POST",
        json_body={"definition": new_definition},
    )
    logger.info(
        f"Published Foundry agent {agent_id} version with Port MCP "
        f"(connection {connection_name})"
    )
    return connection_name


async def remint_port_mcp_for_invoke(
    connections: ProjectConnectionsClient,
    *,
    agent_id: str,
    run: IntegrationRun,
) -> None:
    if not isinstance(run, WorkflowNodeRun):
        raise ActionExecutionError(
            "enablePortMcp requires a workflow run with execution identity"
        )
    access_token = get_run_access_token(run)
    if not access_token:
        raise ActionExecutionError(
            "portAccessToken is required when enablePortMcp is true"
        )

    server_url = required_port_mcp_url()
    connection_name = port_mcp_connection_name(agent_id)
    project_name = project_name_from_endpoint(get_project_endpoint())

    await connections.upsert_bearer_connection(
        project_name=project_name,
        connection_name=connection_name,
        target_url=server_url,
        bearer_token=access_token,
    )
    logger.info(
        f"Reminted Port MCP connection {connection_name} for agent {agent_id} "
        f"(run {run.id})"
    )
