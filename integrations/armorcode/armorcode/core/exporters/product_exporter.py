from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from armorcode.clients.http.armorcode_client import ArmorcodeClient
from armorcode.core.exporters.abstract_exporter import AbstractArmorcodeExporter


class ProductExporter(AbstractArmorcodeExporter[ArmorcodeClient]):
    """Exporter for ArmorCode products."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get paginated products from the API."""
        async for products in self.client.send_paginated_request(
            endpoint="user/product/elastic/paged", method="GET"
        ):
            yield products

    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
        return "product"
