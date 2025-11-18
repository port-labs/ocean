from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from armorcode.clients.http.armorcode_client import ArmorcodeClient
from armorcode.core.exporters.abstract_exporter import AbstractArmorcodeExporter


class FindingExporter(AbstractArmorcodeExporter[ArmorcodeClient]):
    """Exporter for ArmorCode findings."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated findings from the API."""
        async for findings in self.client.send_paginated_request(
            endpoint="api/findings",
            method="POST",
            json_data={},
            use_offset_pagination=False,
        ):
            yield findings
