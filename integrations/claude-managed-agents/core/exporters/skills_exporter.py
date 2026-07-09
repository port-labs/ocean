from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractAnthropicExporter


class SkillsExporter(AbstractAnthropicExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.paginate(
            self.client.beta.skills.list(source="custom")
        ):
            logger.debug(f"Fetched skills batch with {len(batch)} records")
            yield batch
