from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractAnthropicExporter


class EnvironmentsExporter(AbstractAnthropicExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.get_environments():
            logger.debug(f"Fetched environments batch with {len(batch)} records")
            yield batch
