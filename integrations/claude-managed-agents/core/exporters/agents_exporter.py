from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractAnthropicExporter


class AgentsExporter(AbstractAnthropicExporter):
    async def get_paginated_resources(
        self, *, include_archived: bool = False
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.paginate(
            self.client.beta.agents.list(include_archived=include_archived)
        ):
            logger.debug(f"Fetched agents batch with {len(batch)} records")
            yield batch
