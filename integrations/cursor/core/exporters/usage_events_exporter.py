from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorAdminOptions


class CursorUsageEventsExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorAdminOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in self.client.get_usage_events_data(options):
            yield batch
