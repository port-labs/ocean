from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from incident_io.clients.client import PAGE_SIZE, IncidentIoClient
from incident_io.core.exporters.abstract_exporter import AbstractIncidentIoExporter
from incident_io.core.options import UserOptions
from incident_io.helpers.utils import safe_resource_id

USERS_ENDPOINT = "v2/users"


class UserExporter(AbstractIncidentIoExporter[IncidentIoClient]):
    async def get_paginated_resources(
        self, options: UserOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params: dict[str, Any] = {}
        if options["include_inactive"]:
            params["include_inactive"] = True
        async for users in self.client.send_paginated_request(
            USERS_ENDPOINT,
            data_key="users",
            params=params,
            page_size=PAGE_SIZE,
        ):
            yield users

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(
            f"{USERS_ENDPOINT}/{safe_resource_id(resource_id)}"
        )
        user = response.get("user")
        return user if isinstance(user, dict) else None
