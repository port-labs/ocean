from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorAnalyticsOptions

TEAM_MODEL_USAGE_PATH = "/analytics/team/models"


class CursorTeamModelUsageExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorAnalyticsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # The team model usage endpoint is not paginated; it returns the full
        # daily breakdown for the requested window in a single response.
        payload = await self.client.send_api_request(
            "GET",
            TEAM_MODEL_USAGE_PATH,
            params={
                "startDate": options["startDate"],
                "endDate": options["endDate"],
            },
        )
        data = payload.get("data", []) or []
        if data:
            yield data
