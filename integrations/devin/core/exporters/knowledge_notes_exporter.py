from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from clients import endpoints
from core.exporters.abstract_exporter import AbstractDevinExporter


class KnowledgeNotesExporter(AbstractDevinExporter):
    async def get_paginated_resources(  # type: ignore[override]
        self,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(endpoints.KNOWLEDGE_NOTES):
            yield page

    async def get_resource(self, resource_id: str) -> RAW_ITEM:
        return await self.client.send_api_request(
            "GET", f"{endpoints.KNOWLEDGE_NOTES}/{resource_id}"
        )
