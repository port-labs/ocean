from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients import endpoints
from core.exporters.abstract_exporter import AbstractDevinExporter
from core.exporters.options import ListPlaybooksOptions


class PlaybooksExporter(AbstractDevinExporter):
    async def get_paginated_resources(  # type: ignore[override]
        self, options: ListPlaybooksOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in self.client.paginate(
            endpoints.PLAYBOOKS,
            params={"include_enterprise": options["include_enterprise"]},
        ):
            yield page
