from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorAdminOptions

USAGE_EVENTS_PATH = "/teams/filtered-usage-events"


class CursorUsageEventsExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorAdminOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for payload in self.client.send_paginated_request(
            "POST",
            USAGE_EVENTS_PATH,
            json_body={
                "startDate": options["startDate"],
                "endDate": options["endDate"],
            },
        ):
            items = payload.get("usageEvents", []) or []
            if items:
                yield items
