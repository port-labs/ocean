from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

from azure_integration.foundry.clients.http.foundry_client import (
    FoundryApiError,
    FoundryHttpClient,
)
from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListAgentsOptions, SingleAgentOptions
from azure_integration.foundry.foundry_incremental import AGENT_INCREMENTAL
from azure_integration.foundry.helpers.agent_enrichment import (
    build_toolbox_enrichment_index,
    enrich_agent_row,
    enrich_agents_from_toolbox,
)
from azure_integration.foundry.helpers.utils import build_foundry_url


class AgentsExporter(FoundryExporter[ListAgentsOptions, SingleAgentOptions]):
    async def get_resource(self, options: SingleAgentOptions) -> dict[str, Any] | None:
        try:
            payload = await self.client.send_api_request(
                self.client.build_url(
                    options.project_endpoint, f"agents/{options.agent_id}"
                ),
                method="GET",
            )
        except FoundryApiError as error:
            if error.status_code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) else None

    @cache_iterator_result()
    async def iter_agent_pages(
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
        enrich_toolbox = options.enrich_toolbox
        cursor = active_incremental_cursor()
        toolbox_index: dict[str, tuple[list[str], list[str]]] = {}
        if enrich_toolbox:
            toolbox_index = await build_toolbox_enrichment_index(
                self.client,
                project_endpoint=project_endpoint,
            )

        async def fetch_agent_summary(
            endpoint: str, agent_id: str
        ) -> dict[str, Any] | None:
            return await self.get_resource(
                SingleAgentOptions(
                    project_endpoint=endpoint,
                    project_id="",
                    agent_id=agent_id,
                )
            )

        async for page in paginate_with_strategy(
            self.iter_agent_pages(project_endpoint),
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
                    enrich_agent_row(
                        item,
                        project_endpoint=project_endpoint,
                        project_id=project_id,
                    )
                )
            if include_versions:
                await self._attach_versions(project_endpoint, batch)
            if enrich_toolbox and batch:
                await enrich_agents_from_toolbox(
                    project_endpoint=project_endpoint,
                    agents=batch,
                    fetch_agent_if_needed=fetch_agent_summary,
                    toolbox_index=toolbox_index,
                )
            yield batch

    async def _attach_versions(
        self,
        project_endpoint: str,
        agents: list[dict[str, Any]],
    ) -> None:
        """Attach full version history as ``__versions`` (keeps API ``versions.latest`` intact)."""
        for agent in agents:
            agent_id = agent["id"]
            try:
                versions_payload = await self.client.send_api_request(
                    build_foundry_url(project_endpoint, f"agents/{agent_id}/versions")
                )
            except FoundryApiError as error:
                if error.status_code == 404:
                    agent["__versions"] = []
                    continue
                raise
            agent["__versions"] = self.client.items_from_payload(versions_payload)
