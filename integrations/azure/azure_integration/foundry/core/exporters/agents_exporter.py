from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListAgentsOptions
from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL
from azure_integration.foundry.helpers.utils import enrich_with_project


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
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        include_versions = options.include_versions
        cursor = active_incremental_cursor()

        async for page in paginate_with_strategy(
            self._iter_agent_pages(project_endpoint),
            cursor=cursor,
            strategy=AGENT_INCREMENTAL,
        ):
            batch = [
                enrich_with_project(
                    dict(item),
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if include_versions:
                batch = await _attach_versions(self.client, project_endpoint, batch)
            if batch:
                yield batch


def _version_with_identity(
    item: dict[str, Any], agent_id: str
) -> dict[str, Any]:
    """Stable Port identifier for itemsToParse; leave the rest of the payload raw."""
    version = item.get("version") or item.get("id")
    version_str = str(version) if version is not None else ""
    out = dict(item)
    out["agent_id"] = agent_id
    out["id"] = f"{agent_id}/{version_str}" if version_str else agent_id
    return out


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
            _version_with_identity(item, agent_id_str)
            for item in client.items_from_payload(versions_payload)
        ]
        enriched.append(copy)
    return enriched
