from typing import Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorAnalyticsOptions

USER_MODEL_USAGE_PATH = "/analytics/by-user/models"


class CursorUserModelUsageExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorAnalyticsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for payload in self.client.send_paginated_request(
            "GET",
            USER_MODEL_USAGE_PATH,
            params={
                "startDate": options["startDate"],
                "endDate": options["endDate"],
            },
        ):
            # `data` maps each user email to a list of their daily breakdowns;
            # flatten it into per-user-day records carrying the owning email.
            data: dict[str, Any] = payload.get("data", {}) or {}
            items = [
                {"userEmail": email, **record}
                for email, records in data.items()
                for record in (records or [])
            ]
            if items:
                yield items
