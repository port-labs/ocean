from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from armorcode.core.exporters.abstract_exporter import AbstractArmorcodeExporter


class ProductExporter(AbstractArmorcodeExporter):
    """Exporter for ArmorCode products."""

    async def get_paginated_resources(self, options: Optional[Dict[str, Any]] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:  # type: ignore[override]
        """Get paginated products from the API."""
        async for products in self.client.send_paginated_request(
            endpoint="user/product/elastic/paged",
            method="GET",
            content_key="content",
            is_last_key="last",
        ):
            yield products

    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
        return "product"
