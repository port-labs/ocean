from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListPlatformCostReportOptions


class ClaudePlatformCostExporter(AbstractClaudeExporter):
    """Per-day spend from the Claude Platform cost report."""

    ENDPOINT = "/v1/organizations/cost_report"

    async def get_paginated_resources(
        self, options: ListPlatformCostReportOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "starting_at": options["starting_at"],
            "limit": options["limit"],
        }

        bucket_width = options.get("bucket_width")
        if bucket_width:
            params["bucket_width"] = bucket_width

        async for batch in self.client.send_paginated_request(self.ENDPOINT, params):
            logger.debug(f"Fetched platform cost batch with {len(batch)} records")
            yield batch
