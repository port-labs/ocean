from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from incident_io.clients.client import PAGE_SIZE, IncidentIoClient
from incident_io.core.exporters.abstract_exporter import AbstractIncidentIoExporter
from incident_io.helpers.utils import safe_resource_id

TEAMS_ENDPOINT = "v3/teams"


class TeamExporter(AbstractIncidentIoExporter[IncidentIoClient]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for teams in self.client.send_paginated_request(
            TEAMS_ENDPOINT,
            data_key="teams",
            page_size=PAGE_SIZE,
        ):
            yield teams

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(
            f"{TEAMS_ENDPOINT}/{safe_resource_id(resource_id)}"
        )
        team = response.get("team")
        return team if isinstance(team, dict) else None
