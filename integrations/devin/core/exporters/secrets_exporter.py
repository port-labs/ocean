from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients import endpoints
from clients.devin_client import DevinClient


class SecretsExporter:
    """Secret metadata only: the Devin API never returns secret values."""

    def __init__(self, client: DevinClient) -> None:
        self.client = client

    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(endpoints.SECRETS):
            yield page
