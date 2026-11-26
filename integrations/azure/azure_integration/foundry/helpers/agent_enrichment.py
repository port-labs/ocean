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
    ToolboxesExporter,
)
from azure_integration.foundry.core.options import ListToolboxesOptions
from azure_integration.foundry.helpers.toolbox import toolbox_name_from_agent_tools
from azure_integration.foundry.helpers.utils import (
    enrich_with_project,
    tools_from_agent_payload,
)
from azure_integration.foundry.models.base import FoundryModel
from port_ocean.utils.cache import cache_coroutine_result


class AgentLatestSnapshot(FoundryModel):
    version: str | int | None = None


class AgentVersionsSnapshot(FoundryModel):
    latest: AgentLatestSnapshot | None = None


class AgentRowSnapshot(FoundryModel):
    """Subset of agent GET payload used for portal URL and toolbox enrichment."""

    name: str | None = None
    versions: AgentVersionsSnapshot | None = None


def _latest_version_from_agent(agent: dict[str, Any]) -> str | int | None:
    try:
        row = AgentRowSnapshot.model_validate(agent)
    except ValidationError:
        return None
    latest = row.versions.latest if row.versions else None
    return latest.version if latest else None


def _guid_to_base64url(guid: str) -> str:
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
    encoded_sub = _guid_to_base64url(project.subscription_id)
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
        url = foundry_portal_agent_url(
            arm_id, name, version=_latest_version_from_agent(enriched)
        )
        if url is not None:
            enriched["__foundryPortalAgentUrl"] = url
    return enriched


async def resolve_project_arm_id(project_endpoint: str) -> str | None:
    from azure_integration.foundry.core.exporters.project_exporter import (
        ProjectExporter,
    )

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


class ToolboxListItem(FoundryModel):
    name: str | None = None
    id: str | None = None


@cache_coroutine_result()
async def _build_toolbox_map(
    client: FoundryHttpClient, project_endpoint: str, project_id: str
) -> dict[str, dict[str, Any]]:
    exporter = ToolboxesExporter(client)
    toolbox_map: dict[str, dict[str, Any]] = {}
    async for page in exporter.get_paginated_resources(
        ListToolboxesOptions(project_endpoint=project_endpoint, project_id=project_id)
    ):
        for item in page:
            try:
                row = ToolboxListItem.model_validate(item)
            except ValidationError:
                continue
            key = row.name or row.id
            if not key:
                continue
            toolbox_map[key] = item
    return toolbox_map


async def enrich_agents_from_toolbox(
    client: FoundryHttpClient,
    project_endpoint: str,
    project_id: str,
    agents: list[dict[str, Any]],
) -> None:
    """Copy toolbox extra raw fields (`__skillNames`, `__mcpUrls`, `__a2aSubagents`, …)."""
    toolbox_map = await _build_toolbox_map(client, project_endpoint, project_id)
    for agent in agents:
        toolbox_name = toolbox_name_from_agent_tools(tools_from_agent_payload(agent))
        if not toolbox_name:
            continue
        toolbox = toolbox_map.get(toolbox_name)
        if toolbox is None:
            continue
        for key, value in toolbox.items():
            if not key.startswith("__") or key.startswith("__foundry"):
                continue
            agent[key] = list(value) if isinstance(value, list) else value
