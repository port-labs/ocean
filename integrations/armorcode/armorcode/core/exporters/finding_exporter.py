from typing import Any, Dict, Optional
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from armorcode.core.exporters.abstract_exporter import AbstractArmorcodeExporter


class FindingExporter(AbstractArmorcodeExporter):
    """Exporter for ArmorCode findings."""

    async def get_paginated_resources(self, options: Optional[Dict[str, Any]] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:  # type: ignore[override]
        """Get paginated findings from the API."""
        async for findings in self.client.send_paginated_request(
            endpoint="api/findings",
            method="POST",
            content_key="findings",
            is_last_key=None,
            json_data={},
            use_offset_pagination=False,
        ):
            yield findings

    def get_resource_kind(self) -> str:
        """Get the resource kind this exporter handles."""
        return "finding"
