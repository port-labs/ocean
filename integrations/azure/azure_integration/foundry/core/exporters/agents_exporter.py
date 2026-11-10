from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListAgentsOptions
from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL
from azure_integration.foundry.helpers.utils import (
    build_foundry_url,
    enrich_with_project,
)


class AgentsExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    @cache_iterator_result()
    async def _iter_agent_pages(
        self, project_endpoint: str
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Bare agents list, cached for the current event (shared across agent resources)."""
        # List agents supports order=asc|desc by created_at only.
        params = AGENT_INCREMENTAL.merge_params(
            {"limit": FoundryHttpClient.PAGE_SIZE}, None
        )
        async for page in self.client.send_cursor_paginated_request(
            project_endpoint,
            "agents",
            params=params,
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
                    item,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if include_versions:
                await _attach_versions(self.client, project_endpoint, batch)
            yield batch


async def _attach_versions(
    client: FoundryHttpClient,
    project_endpoint: str,
    agents: list[dict[str, Any]],
) -> None:
    """Attach full version history as ``__versions`` (keeps API ``versions.latest`` intact)."""
    for agent in agents:
        if not agent.get("id"):
            continue
        versions_payload = await client.send_api_request(
            build_foundry_url(project_endpoint, f"agents/{agent["id"]}/versions")
        )
        agent["__versions"] = client.items_from_payload(versions_payload)
