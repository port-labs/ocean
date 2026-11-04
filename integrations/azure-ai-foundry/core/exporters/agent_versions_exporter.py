from __future__ import annotations

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.http.base_client import BaseFoundryClient
from clients.http.foundry_client import FoundryHttpClient
from clients.quota_client import create_quota_client
from core.exporters.abstract_exporter import AbstractFoundryExporter
from helpers.metadata import (
    get_source_platform_name,
    merge_metadata,
    owner_from_metadata,
)
from helpers.project_scope import enrich_with_project, get_project_endpoint
from helpers.utils import region_from_project_endpoint, timestamp_to_iso
from foundry_incremental import AGENT_VERSION_INCREMENTAL


class AgentVersionsExporter(AbstractFoundryExporter[FoundryHttpClient]):
    async def get_paginated_resources(self, **_options: object) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor = active_incremental_cursor()
        params = AGENT_VERSION_INCREMENTAL.merge_params({}, cursor)
        quota = create_quota_client()
        project_endpoint = get_project_endpoint()

        agents_payload = await self.client.send_api_request(
            self.client.build_url(project_endpoint, "agents"),
            params={"limit": BaseFoundryClient.PAGE_SIZE},
        )
        agents = self.client.items_from_payload(agents_payload)
        if not agents:
            logger.info("No agents found; skipping agent version export")
            return

        for agent in agents:
            agent_name = agent.get("name") or agent.get("id")
            if not agent_name:
                continue
            agent_name_str = str(agent_name)
            versions_payload = await self.client.send_api_request(
                self.client.build_url(
                    project_endpoint, f"agents/{agent_name_str}/versions"
                ),
                params={"limit": BaseFoundryClient.PAGE_SIZE},
            )
            versions = self.client.items_from_payload(versions_payload)
            if not versions:
                latest = agent.get("versions")
                if isinstance(latest, dict) and isinstance(latest.get("latest"), dict):
                    versions = [latest["latest"]]

            async for page in paginate_with_strategy(
                _version_pages(versions, agent_name_str),
                cursor=cursor,
                strategy=AGENT_VERSION_INCREMENTAL,
            ):
                check = await quota.check_before_batch(
                    region=region_from_project_endpoint(project_endpoint),
                    batch_size=len(page),
                )
                if not check.allowed:
                    logger.warning(
                        f"Skipping agent-version batch for {agent_name_str}: "
                        f"{check.message}"
                    )
                    continue
                batch = [
                    enrich_with_project(_normalize_agent_version(item, agent_name_str))
                    for item in page
                ]
                if batch:
                    yield batch


async def _version_pages(
    versions: list[dict[str, object]], agent_id: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if versions:
        yield versions


def _normalize_agent_version(
    item: dict[str, object], agent_id: str
) -> dict[str, object]:
    normalized = dict(item)
    version_number = item.get("version") or item.get("id")
    version_str = str(version_number) if version_number is not None else ""
    normalized["agent_id"] = agent_id
    normalized["id"] = f"{agent_id}/{version_str}" if version_str else agent_id
    normalized["source_platform"] = get_source_platform_name()

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

    metadata = merge_metadata(item.get("metadata"))
    if metadata:
        normalized["metadata"] = metadata
        owner = owner_from_metadata(metadata)
        if owner:
            normalized["owner"] = owner

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
