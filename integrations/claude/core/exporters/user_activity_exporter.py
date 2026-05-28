from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeUserActivityOptions


class ClaudeUserActivityExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeUserActivityOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "date": options["date"],
            "limit": options["limit"],
        }

        async for batch in self.client.get_user_activity(params):
            logger.debug(f"Fetched user activity batch with {len(batch)} records")
            yield batch
