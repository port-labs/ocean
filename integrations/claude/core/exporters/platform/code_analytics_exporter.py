from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListPlatformCodeAnalyticsOptions


class ClaudePlatformCodeAnalyticsExporter(AbstractClaudeExporter):
    """Per-day Claude Code analytics from the Claude Platform report.

    Soft-fails (yields nothing) when Claude Code is not enabled for the
    organisation (HTTP 403), rather than crashing the resync.
    """

    ENDPOINT = "/v1/organizations/usage_report/claude_code"

    async def get_paginated_resources(
        self, options: ListPlatformCodeAnalyticsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "starting_at": options["starting_at"],
            "limit": options["limit"],
        }

        async for batch in self.client.send_paginated_request(
            self.ENDPOINT, params, soft_fail_statuses={403}
        ):
            logger.debug(
                f"Fetched platform code analytics batch with {len(batch)} records"
            )
            yield batch
