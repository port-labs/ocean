from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeActivitySummaryOptions


class ClaudeActivitySummaryExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeActivitySummaryOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params: dict = {"starting_date": options["starting_date"]}
        ending_date = options.get("ending_date")
        if ending_date:
            params["ending_date"] = ending_date

        records = await self.client.get_activity_summary(params)
        if records:
            logger.debug(f"Fetched {len(records)} activity summary records")
            yield records
