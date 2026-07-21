from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.endpoints import V1_AGENTS
from core.exporters.abstract_exporter import AbstractCursorExporter


class AgentsExporter(AbstractCursorExporter):
    """Syncs the `agent` kind from the v1 List Agents API."""

    async def get_paginated_resources(
        self, *, include_archived: bool = False
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query_params = {"includeArchived": include_archived}
        async for batch in self.client.paginate_by_cursor(
            V1_AGENTS, "items", params=query_params
        ):
            logger.debug(f"Fetched Cursor agents batch with {len(batch)} records")
            yield batch
