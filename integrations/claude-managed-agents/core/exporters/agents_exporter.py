from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractAnthropicExporter


class AgentsExporter(AbstractAnthropicExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.get_agents():
            logger.debug(f"Fetched agents batch with {len(batch)} records")
            yield batch
