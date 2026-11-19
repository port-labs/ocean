from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients import endpoints
from core.exporters.abstract_exporter import AbstractDevinExporter


class SecretsExporter(AbstractDevinExporter):
    """Secret metadata only: the Devin API never returns secret values."""

    async def get_paginated_resources(  # type: ignore[override]
        self,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(endpoints.SECRETS):
            yield page
