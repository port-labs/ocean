from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeCostReportOptions


class ClaudeCostExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeCostReportOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "starting_at": options["starting_at"],
            "limit": options["limit"],
        }

        bucket_width = options.get("bucket_width")
        if bucket_width:
            params["bucket_width"] = bucket_width

        async for batch in self.client.get_cost_report(params):
            logger.debug(f"Fetched cost batch with {len(batch)} records")
            yield batch
