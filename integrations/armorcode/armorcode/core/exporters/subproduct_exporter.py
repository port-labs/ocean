from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from armorcode.clients.http.armorcode_client import ArmorcodeClient
from armorcode.core.exporters.abstract_exporter import AbstractArmorcodeExporter


class SubProductExporter(AbstractArmorcodeExporter[ArmorcodeClient]):
    """Exporter for ArmorCode subproducts."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated subproducts from the API."""
        async for subproducts in self.client.send_paginated_request(
            endpoint="user/sub-product/elastic", method="GET"
        ):
            yield subproducts

    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
        return "sub-product"
