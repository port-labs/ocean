from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeUserUsageReportOptions


class ClaudeUserUsageReportExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeUserUsageReportOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params: dict = {
            "starting_at": options["starting_at"],
            "limit": options["limit"],
        }

        ending_at = options.get("ending_at")
        if ending_at:
            params["ending_at"] = ending_at

        order_by = options.get("order_by")
        if order_by:
            params["order_by"] = order_by

        group_by = options.get("group_by", [])
        if group_by:
            params["group_by[]"] = group_by

        async for batch in self.client.get_user_usage_report(params):
            logger.debug(f"Fetched user usage report batch with {len(batch)} records")
            yield batch
