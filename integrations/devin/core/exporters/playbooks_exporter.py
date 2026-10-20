from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from clients import endpoints
from core.exporters.abstract_exporter import AbstractDevinExporter


class PlaybooksExporter(AbstractDevinExporter):
    async def get_paginated_resources(  # type: ignore[override]
        self, *, include_enterprise: bool = False
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(
            endpoints.PLAYBOOKS, params={"include_enterprise": include_enterprise}
        ):
            yield page

    async def get_resource(self, resource_id: str) -> RAW_ITEM:
        return await self.client.send_api_request(
            "GET", f"{endpoints.PLAYBOOKS}/{resource_id}"
        )
