from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorAdminOptions

DAILY_USAGE_PATH = "/teams/daily-usage-data"


class CursorDailyUsageExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorAdminOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for payload in self.client.send_paginated_request(
            "POST",
            DAILY_USAGE_PATH,
            json_body={
                "startDate": options["startDate"],
                "endDate": options["endDate"],
            },
            page_size=options["pageSize"],
        ):
            items = payload.get("data", []) or []
            if items:
                yield items
