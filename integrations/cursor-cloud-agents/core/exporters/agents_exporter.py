from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.cache import cache_iterator_result

from clients.endpoints import V1_AGENTS, v1_agent_usage
from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListAgentOptions


class AgentsExporter(AbstractCursorExporter):
    """Syncs the `agent` kind from the v1 List Agents API."""

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListAgentOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query_params = {"includeArchived": options.include_archived}
        async for batch in self.client.paginate_by_cursor(
            V1_AGENTS, "items", params=query_params
        ):
            logger.debug(f"Fetched Cursor agents batch with {len(batch)} records")
            yield batch

    async def get_runs_usage_map_for_agent(self, agent_id: str) -> dict[str, Any]:
        try:
            usage_response = await self.client.send_api_request(
                "GET", v1_agent_usage(agent_id)
            )
        except Exception as error:
            logger.warning(
                f"Failed to fetch token usage for Cursor agent {agent_id} "
                f"(runs will sync without usage): {error}"
            )
            return {}
        runs = usage_response.get("runs")
        if not isinstance(runs, list):
            return {}

        usage_by_run_id: dict[str, Any] = {}
        for run_usage in runs:
            if not isinstance(run_usage, dict):
                continue
            run_id = run_usage.get("id")
            usage = run_usage.get("usage")
            if isinstance(run_id, str) and run_id and usage is not None:
                usage_by_run_id[run_id] = usage
        return usage_by_run_id
