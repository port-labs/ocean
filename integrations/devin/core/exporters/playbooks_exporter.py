from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients import endpoints
from clients.devin_client import DevinClient
from core.exporters.options import PlaybooksExportOptions


class PlaybooksExporter:
    def __init__(self, client: DevinClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: PlaybooksExportOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(
            endpoints.PLAYBOOKS,
            params={"include_enterprise": options.include_enterprise},
        ):
            yield page
