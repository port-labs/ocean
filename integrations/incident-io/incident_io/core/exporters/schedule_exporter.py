from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from incident_io.clients.client import IncidentIoClient
from incident_io.core.exporters.abstract_exporter import AbstractIncidentIoExporter
from incident_io.helpers.utils import safe_resource_id

SCHEDULES_ENDPOINT = "v2/schedules"
# current_shifts is who is on call now. next_shifts is omitted when page_size
# is greater than 25.
SCHEDULE_PAGE_SIZE = 25


class ScheduleExporter(AbstractIncidentIoExporter[IncidentIoClient]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for schedules in self.client.send_paginated_request(
            SCHEDULES_ENDPOINT,
            data_key="schedules",
            page_size=SCHEDULE_PAGE_SIZE,
        ):
            yield schedules

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(
            f"{SCHEDULES_ENDPOINT}/{safe_resource_id(resource_id)}"
        )
        schedule = response.get("schedule")
        return schedule if isinstance(schedule, dict) else None
