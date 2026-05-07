from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeCodeAnalyticsOptions


class ClaudeCodeAnalyticsExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeCodeAnalyticsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "starting_at": options["starting_at"],
            "limit": options["limit"],
        }

        async for batch in self.client.get_claude_code_report(params):
            logger.debug(f"Fetched code analytics batch with {len(batch)} records")
            yield batch
