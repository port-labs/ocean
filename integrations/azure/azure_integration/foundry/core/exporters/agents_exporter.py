from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListAgentsOptions
from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL
from azure_integration.foundry.helpers.utils import (
    build_foundry_url,
    enrich_with_project,
)


class AgentsExporter(FoundryExporter):
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
            batch: list[dict[str, Any]] = []
            for item in page:
                agent_id = item.get("id")
                if not agent_id:
                    logger.warning(
                        "Skipping Foundry agent missing required id field",
                        agent=item,
                        project_endpoint=project_endpoint,
                    )
                    continue
                batch.append(
                    enrich_with_project(
                        item,
                        project_endpoint=project_endpoint,
                        project_id=project_id,
                    )
                )
            if include_versions:
                await self._attach_versions(project_endpoint, batch)
            yield batch

<<<<<<< HEAD
    async def _attach_versions(
        self,
        project_endpoint: str,
        agents: list[dict[str, Any]],
    ) -> None:
        """Attach full version history as ``__versions`` (keeps API ``versions.latest`` intact)."""
        for agent in agents:
            agent_id = agent["id"]
            versions_payload = await self.client.send_api_request(
                build_foundry_url(project_endpoint, f"agents/{agent_id}/versions")
            )
            agent["__versions"] = self.client.items_from_payload(versions_payload)
=======

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
>>>>>>> 67915c0ec (Address Foundry catalog CR: simplify HTTP client and resync dispatch.)
