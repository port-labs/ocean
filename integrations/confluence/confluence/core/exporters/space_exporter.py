from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import RAW_ITEM

from confluence.clients.client import ConfluenceClient
from confluence.core.exporters.abstract_exporter import AbstractConfluenceExporter
from confluence.core.options import SpaceExportOptions
from confluence.helpers.utils import attach_web_url


class SpaceExporter(AbstractConfluenceExporter[ConfluenceClient]):
    """Exports spaces from ``GET /wiki/api/v2/spaces``.

    Type, status, and labels are sent only when the selector sets them.
    Otherwise Confluence returns every space.
    """

    async def get_paginated_resources(
        self, options: SpaceExportOptions | None = None
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        selected = options or SpaceExportOptions()
        params: dict[str, Any] = {"description-format": "plain"}
        if selected.space_type:
            params["type"] = selected.space_type
        if selected.status:
            params["status"] = selected.status
        if selected.labels:
            params["labels"] = ",".join(selected.labels)

        async for batch in self.client.send_paginated_request("spaces", params=params):
            yield [self._enrich(item) for item in batch]

    async def get_single_resource(self, resource_id: str) -> RAW_ITEM | None:
        payload = await self.client.send_api_request(
            f"spaces/{resource_id}",
            params={"description-format": "plain"},
            missing_ok=True,
        )
        return self._enrich(payload) if payload.get("id") else None

    def _enrich(self, item: dict[str, Any]) -> dict[str, Any]:
        return attach_web_url(self.client.site_url, item)
