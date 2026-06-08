from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorAnalyticsOptions


class CursorAiCommitMetricsExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorAnalyticsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.get_ai_commit_metrics(options):
            yield batch
