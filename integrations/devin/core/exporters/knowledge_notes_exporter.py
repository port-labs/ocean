from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients import endpoints
from clients.devin_client import DevinClient


class KnowledgeNotesExporter:
    def __init__(self, client: DevinClient) -> None:
        self.client = client

    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(endpoints.KNOWLEDGE_NOTES):
            yield page
