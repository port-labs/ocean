from __future__ import annotations

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.clients.quota_client import create_quota_client
from azure_integration.foundry.core.exporters.abstract_exporter import AbstractFoundryExporter
from azure_integration.foundry.helpers.metadata import (
    get_source_platform_name,
    merge_metadata,
    owner_from_metadata,
)
from azure_integration.foundry.helpers.project_scope import enrich_with_project, get_project_endpoint
from azure_integration.foundry.helpers.utils import region_from_project_endpoint, timestamp_to_iso
from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL


class AgentsExporter(AbstractFoundryExporter[FoundryHttpClient]):
    async def get_paginated_resources(
        self,
        *,
        include_versions: bool = False,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor = active_incremental_cursor()
        params = AGENT_INCREMENTAL.merge_params({}, cursor)
        quota = create_quota_client()
        project_endpoint = get_project_endpoint()

        async for page in paginate_with_strategy(
            self.client.send_paginated_request(
                project_endpoint, "agents", params=params
            ),
            cursor=cursor,
            strategy=AGENT_INCREMENTAL,
        ):
            check = await quota.check_before_batch(
                region=region_from_project_endpoint(project_endpoint),
                batch_size=len(page),
            )
            if not check.allowed:
                logger.warning(
                    f"Skipping agent batch for {project_endpoint}: {check.message}"
                )
                continue
            batch = [
                enrich_with_project(_normalize_agent(item)) for item in page
            ]
            if include_versions:
                batch = await _attach_versions(self.client, project_endpoint, batch)
            yield batch


def _normalize_agent(item: dict[str, object]) -> dict[str, object]:
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

    metadata = merge_metadata(item.get("metadata"), latest_version.get("metadata"))
    if metadata:
        normalized["metadata"] = metadata
        owner = owner_from_metadata(metadata)
        if owner:
            normalized["owner"] = owner

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
        blueprint_id = blueprint_reference.get("blueprint_id") or blueprint_reference.get(
            "blueprintId"
        )
        if blueprint_id is not None:
            normalized["identity_blueprint_id"] = str(blueprint_id)

    normalized["source_platform"] = get_source_platform_name()

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


async def _attach_versions(
    client: FoundryHttpClient,
    project_endpoint: str,
    agents: list[dict[str, object]],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for agent in agents:
        agent_id = agent.get("id") or agent.get("name")
        if not agent_id:
            enriched.append(agent)
            continue
        versions_payload = await client.send_api_request(
            client.build_url(project_endpoint, f"agents/{agent_id}/versions")
        )
        versions = client.items_from_payload(versions_payload)
        copy = dict(agent)
        copy["versions"] = versions
        enriched.append(copy)
    return enriched
