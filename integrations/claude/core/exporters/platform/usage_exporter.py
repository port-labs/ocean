from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListPlatformUsageReportOptions


class ClaudePlatformUsageExporter(AbstractClaudeExporter):
    """Per-day API message usage from the Claude Platform usage report."""

    ENDPOINT = "/v1/organizations/usage_report/messages"

    async def get_paginated_resources(
        self, options: ListPlatformUsageReportOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "starting_at": options["starting_at"],
            "limit": options["limit"],
        }

        bucket_width = options.get("bucket_width")
        if bucket_width:
            params["bucket_width"] = bucket_width

        group_by = options.get("group_by", [])
        if group_by:
            params["group_by[]"] = group_by

        async for batch in self.client.send_paginated_request(self.ENDPOINT, params):
            logger.debug(f"Fetched platform usage batch with {len(batch)} records")
            yield batch
