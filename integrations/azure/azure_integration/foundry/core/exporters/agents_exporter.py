from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListAgentsOptions
from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL
from azure_integration.foundry.helpers.utils import enrich_with_project, timestamp_to_iso


class AgentsExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    @cache_iterator_result()
    async def _iter_agent_pages(
        self, project_endpoint: str
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Bare agents list, cached for the current event (shared across agent resources)."""
        async for page in self.client.send_paginated_request(
            project_endpoint,
            "agents",
            params={"limit": FoundryHttpClient.PAGE_SIZE},
        ):
            yield page

    async def get_paginated_resources(
        self, options: ListAgentsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options["project_endpoint"]
        project_id = options["project_id"]
        include_versions = bool(options.get("include_versions", False))
        cursor = active_incremental_cursor()

        async for page in paginate_with_strategy(
            self._iter_agent_pages(project_endpoint),
            cursor=cursor,
            strategy=AGENT_INCREMENTAL,
        ):
            batch = [
                enrich_with_project(
                    _normalize_agent(item),
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if include_versions:
                batch = await _attach_versions(self.client, project_endpoint, batch)
            if batch:
                yield batch


def _normalize_agent(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    agent_id = item.get("id") or item.get("name")
    if agent_id is not None:
        normalized.setdefault("id", agent_id)

    status = item.get("status") or item.get("state")
    if status is not None:
        normalized["status"] = status

    latest = item.get("versions")
    latest_version: dict[str, object] = {}
    if isinstance(latest, dict):
        candidate = latest.get("latest")
        if isinstance(candidate, dict):
            latest_version = candidate

    definition = latest_version.get("definition")
    if isinstance(definition, dict):
        agent_kind = definition.get("kind")
        if agent_kind is not None:
            normalized["kind"] = agent_kind
        if definition.get("model") is not None:
            normalized["model"] = definition["model"]
        if "instructions" in definition:
            normalized["instructions"] = definition["instructions"]
        tools = definition.get("tools")
        if isinstance(tools, list):
            normalized["tools"] = tools
            normalized["tool_count"] = len(tools)

    description = latest_version.get("description")
    if description is not None:
        normalized["description"] = description

    instance_identity = latest_version.get("instance_identity")
    if isinstance(instance_identity, dict):
        principal_id = instance_identity.get("principal_id") or instance_identity.get(
            "principalId"
        )
        client_id = instance_identity.get("client_id") or instance_identity.get(
            "clientId"
        )
        identity_status = instance_identity.get("status")
        if principal_id is not None:
            normalized["entra_principal_id"] = str(principal_id)
        if client_id is not None:
            normalized["entra_client_id"] = str(client_id)
        if identity_status is not None:
            normalized["entra_identity_status"] = str(identity_status)

    blueprint_reference = latest_version.get("blueprint_reference")
    if isinstance(blueprint_reference, dict):
        blueprint_id = blueprint_reference.get(
            "blueprint_id"
        ) or blueprint_reference.get("blueprintId")
        if blueprint_id is not None:
            normalized["identity_blueprint_id"] = str(blueprint_id)

    version_number = latest_version.get("version")
    if version_number is not None:
        normalized["version"] = str(version_number)
    version_status = latest_version.get("status")
    if version_status is not None:
        normalized["version_status"] = version_status

    configuration_state = item.get("configuration_state") or item.get(
        "configurationState"
    )
    if configuration_state is not None:
        normalized["configuration_state"] = configuration_state

    agent_guid = latest_version.get("agent_guid") or latest_version.get("agentGuid")
    if agent_guid is not None:
        normalized["agent_guid"] = str(agent_guid)

    created = latest_version.get("created_at") or item.get("created_at")
    created_iso = timestamp_to_iso(created)
    if created_iso:
        normalized["created_at"] = created_iso

    updated = item.get("updated_at") or item.get("updatedAt")
    updated_iso = timestamp_to_iso(updated)
    if updated_iso:
        normalized["updated_at"] = updated_iso

    return normalized


def _normalize_agent_version(
    item: dict[str, object], agent_id: str
) -> dict[str, object]:
    normalized = dict(item)
    version_number = item.get("version") or item.get("id")
    version_str = str(version_number) if version_number is not None else ""
    normalized["agent_id"] = agent_id
    normalized["id"] = f"{agent_id}/{version_str}" if version_str else agent_id

    definition = item.get("definition")
    if isinstance(definition, dict):
        if definition.get("kind") is not None:
            normalized["kind"] = definition["kind"]
        if definition.get("model") is not None:
            normalized["model"] = definition["model"]
        if "instructions" in definition:
            normalized["instructions"] = definition["instructions"]
        tools = definition.get("tools")
        if isinstance(tools, list):
            normalized["tools"] = tools
            normalized["tool_count"] = len(tools)

    if item.get("description") is not None:
        normalized["description"] = item["description"]
    if item.get("status") is not None:
        normalized["version_status"] = item["status"]
    if version_str:
        normalized["version"] = version_str

    instance_identity = item.get("instance_identity")
    if isinstance(instance_identity, dict):
        principal_id = instance_identity.get("principal_id") or instance_identity.get(
            "principalId"
        )
        client_id = instance_identity.get("client_id") or instance_identity.get(
            "clientId"
        )
        if principal_id is not None:
            normalized["entra_principal_id"] = str(principal_id)
        if client_id is not None:
            normalized["entra_client_id"] = str(client_id)

    created_iso = timestamp_to_iso(item.get("created_at") or item.get("createdAt"))
    if created_iso:
        normalized["created_at"] = created_iso
    updated_iso = timestamp_to_iso(item.get("updated_at") or item.get("updatedAt"))
    if updated_iso:
        normalized["updated_at"] = updated_iso

    if item.get("draft") is not None:
        normalized["is_draft"] = bool(item["draft"])

    return normalized


async def _attach_versions(
    client: FoundryHttpClient,
    project_endpoint: str,
    agents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for agent in agents:
        agent_id = agent.get("id") or agent.get("name")
        if not agent_id:
            enriched.append(agent)
            continue
        agent_id_str = str(agent_id)
        versions_payload = await client.send_api_request(
            client.build_url(project_endpoint, f"agents/{agent_id_str}/versions")
        )
        copy = dict(agent)
        copy["versions"] = [
            _normalize_agent_version(item, agent_id_str)
            for item in client.items_from_payload(versions_payload)
        ]
        enriched.append(copy)
    return enriched
