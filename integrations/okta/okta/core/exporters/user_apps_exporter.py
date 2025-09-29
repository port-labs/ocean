from typing import Any

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class OktaUserAppsExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for a user's applications in Okta."""

    async def get_resource(self, user_id: str) -> dict[str, Any]:
        apps = await self.client.get_list_resource(f"users/{user_id}/appLinks")
        return {"applications": apps}

    def get_paginated_resources(self, user_id: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError(
            "Pagination is not supported for user applications endpoint"
        )
