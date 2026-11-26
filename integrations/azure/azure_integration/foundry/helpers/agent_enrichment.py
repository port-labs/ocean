from __future__ import annotations

import base64
import uuid
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.exporters.project_exporter import (
    foundry_project_from_arm_id,
)
from azure_integration.foundry.core.exporters.toolboxes_exporter import (
    ToolboxPayload,
    ToolboxesExporter,
)
from azure_integration.foundry.core.options import SingleToolboxOptions
from azure_integration.foundry.helpers.a2a import skill_names_from_refs
from azure_integration.foundry.helpers.toolbox import toolbox_name_from_agent_tools
from azure_integration.foundry.helpers.utils import enrich_with_project
from azure_integration.foundry.models.toolbox import TOOLBOX_SERVER_LABEL, Tool


def guid_to_base64url(guid: str) -> str:
    """Foundry portal route segment for a subscription GUID (base64url, no padding)."""
    try:
        raw = uuid.UUID(guid).bytes
    except ValueError:
        return guid
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def foundry_portal_agent_url(
    project_arm_id: str,
    agent_name: str,
    *,
    version: str | int | None = None,
) -> str | None:
    """https://ai.azure.com/nextgen/r/.../build/agents/{name}/build?version={n}"""
    project = foundry_project_from_arm_id(project_arm_id)
    if project is None or not agent_name.strip():
        return None
    encoded_sub = guid_to_base64url(project.subscription_id)
    route = (
        f"{encoded_sub},{project.resource_group_name},,"
        f"{project.account_name},{project.project_name}"
    )
    path_name = quote(agent_name, safe="")
    base = f"https://ai.azure.com/nextgen/r/{route}/build/agents/{path_name}/build"
    if version is None or version == "":
        return base
    return f"{base}?version={quote(str(version), safe='')}"


def enrich_agent_row(
    agent: dict[str, Any],
    *,
    project_endpoint: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Project identity + Foundry portal URL; same shape for resync and catalog register."""
    enriched = enrich_with_project(
        agent,
        project_endpoint=project_endpoint,
        project_id=project_id,
    )
    arm_id, name = enriched.get("__foundryProjectId"), enriched.get("name")
    if isinstance(arm_id, str) and isinstance(name, str):
        version = None
        versions = enriched.get("versions")
        if isinstance(versions, dict):
            latest = versions.get("latest")
            if isinstance(latest, dict):
                version = latest.get("version")
        url = foundry_portal_agent_url(arm_id, name, version=version)
        if url is not None:
            enriched["__foundryPortalAgentUrl"] = url
    return enriched


async def resolve_project_arm_id(project_endpoint: str) -> str | None:
    from azure_integration.foundry.core.exporters.project_exporter import ProjectExporter

    try:
        project = await ProjectExporter().find_by_endpoint(project_endpoint)
    except ValueError:
        return None
    return project.project_arm_id


async def prepare_agent_for_catalog(
    agent: dict[str, Any],
    *,
    project_endpoint: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Enrich one agent row before ``register_entity`` (resolves ARM id when missing)."""
    arm_id = project_id or await resolve_project_arm_id(project_endpoint)
    return enrich_agent_row(
        agent,
        project_endpoint=project_endpoint,
        project_id=arm_id,
    )


def _definition_tools(agent: dict[str, Any]) -> list[Any]:
    versions = agent.get("versions")
    if not isinstance(versions, dict):
        return []
    latest = versions.get("latest")
    if not isinstance(latest, dict):
        return []
    definition = latest.get("definition")
    if not isinstance(definition, dict):
        return []
    tools = definition.get("tools")
    return tools if isinstance(tools, list) else []


def mcp_servers_from_tools(tools: list[Any]) -> list[str]:
    """MCP endpoints from toolbox tools: server_url when set, else label (never the toolbox gateway)."""
    servers: list[str] = []
    for raw in tools:
        if not isinstance(raw, dict) or raw.get("type") != "mcp":
            continue
        try:
            tool = Tool.model_validate(raw)
        except Exception:
            continue
        if tool.toolbox_name is not None:
            continue
        if tool.server_url and tool.server_url.strip():
            servers.append(tool.server_url.strip())
            continue
        label = tool.server_label or raw.get("name")
        if label and str(label) != TOOLBOX_SERVER_LABEL:
            servers.append(str(label))
    return servers


def _enrichment_from_toolbox_payload(
    toolbox: dict[str, Any],
) -> tuple[list[str], list[str]]:
    try:
        parsed = ToolboxPayload.model_validate(toolbox)
    except ValidationError:
        return [], []
    latest = parsed.versions.latest if parsed.versions else None
    if latest is None:
        return [], []
    return skill_names_from_refs(latest.skills), mcp_servers_from_tools(latest.tools)


async def enrich_agents_from_toolbox(
    *,
    client: FoundryHttpClient,
    project_endpoint: str,
    agents: list[dict[str, Any]],
    fetch_agent_if_needed: Any | None,
) -> None:
    """Set __toolboxSkillNames and __toolboxMcpServers when the agent pins a toolbox MCP."""
    exporter = ToolboxesExporter(client)
    by_name: dict[str, tuple[list[str], list[str]]] = {}

    async def enrichment_for(toolbox_name: str) -> tuple[list[str], list[str]]:
        if toolbox_name in by_name:
            return by_name[toolbox_name]
        loaded = await exporter.get_resource(
            SingleToolboxOptions(
                project_endpoint=project_endpoint,
                project_id="",
                toolbox_name=toolbox_name,
            )
        )
        by_name[toolbox_name] = _enrichment_from_toolbox_payload(loaded or {})
        return by_name[toolbox_name]

    for agent in agents:
        tools = _definition_tools(agent)
        if not tools and fetch_agent_if_needed is not None:
            detail = await fetch_agent_if_needed(project_endpoint, str(agent.get("id")))
            if isinstance(detail, dict):
                agent.setdefault("versions", detail.get("versions"))
                tools = _definition_tools(agent)
        toolbox_name = toolbox_name_from_agent_tools(tools)
        if not toolbox_name:
            agent["__toolboxSkillNames"] = []
            agent["__toolboxMcpServers"] = []
            continue
        skills, mcp_servers = await enrichment_for(toolbox_name)
        agent["__toolboxSkillNames"] = list(skills)
        agent["__toolboxMcpServers"] = list(mcp_servers)
