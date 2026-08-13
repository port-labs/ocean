from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractCursorExporter
from core.options import ListCursorTeamSkillUsageOptions

TEAM_SKILL_USAGE_PATH = "/analytics/team/skills"


class CursorTeamSkillUsageExporter(AbstractCursorExporter):
    async def get_paginated_resources(
        self, options: ListCursorTeamSkillUsageOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # The team skills endpoint is not paginated; it returns the full daily
        # breakdown for the requested window in a single response.
        params: dict[str, str] = {
            "startDate": options["startDate"],
            "endDate": options["endDate"],
        }
        if users := options.get("users"):
            params["users"] = users

        payload = await self.client.send_api_request(
            "GET",
            TEAM_SKILL_USAGE_PATH,
            params=params,
        )
        data = payload.get("data", []) or []
        if data:
            yield data
