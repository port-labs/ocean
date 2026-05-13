from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeUsageReportOptions


class ClaudeUsageExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeUsageReportOptions
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

        async for batch in self.client.get_usage_report_messages(params):
            logger.debug(f"Fetched usage batch with {len(batch)} records")
            yield batch
