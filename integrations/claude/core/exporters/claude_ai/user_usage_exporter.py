from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.exporters.claude_ai.analytics_params import build_analytics_query_params
from core.options import ListUserReportOptions


class ClaudeAIUserUsageExporter(AbstractClaudeExporter):
    """Per-user token usage across a date range (Claude AI / Enterprise).

    The report rows carry a null ``starting_at`` / ``ending_at``; the resolved
    query range is stamped onto each record so entities have a stable date.
    """

    ENDPOINT = "/v1/organizations/analytics/user_usage_report"

    async def get_paginated_resources(
        self, options: ListUserReportOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = build_analytics_query_params(options)
        starting_at = options["starting_at"]
        ending_at = options["ending_at"]

        async for batch in self.client.send_paginated_request(
            self.ENDPOINT, params, soft_fail_statuses={403}
        ):
            for record in batch:
                record["__starting_at"] = starting_at
                record["__ending_at"] = ending_at
            logger.debug(f"Fetched user usage batch with {len(batch)} records")
            yield batch
