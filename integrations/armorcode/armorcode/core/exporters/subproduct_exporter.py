from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from armorcode.core.exporters.abstract_exporter import AbstractArmorcodeExporter


class SubProductExporter(AbstractArmorcodeExporter):
    """Exporter for ArmorCode subproducts."""

    async def get_paginated_resources(self, options: Optional[Dict[str, Any]] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:  # type: ignore[override]
        """Get paginated subproducts from the API."""
        async for subproducts in self.client.send_paginated_request(
            endpoint="user/sub-product/elastic",
            method="GET",
            content_key="content",
            is_last_key="last",
        ):
            yield subproducts

    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
        return "sub-product"
