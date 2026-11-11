from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import RAW_ITEM

from confluence.clients.client import ConfluenceClient
from confluence.core.exporters.abstract_exporter import AbstractConfluenceExporter
from confluence.core.options import PageExportOptions
from confluence.helpers.utils import attach_web_url

BODY_PAGE_SIZE = 25


class PageExporter(AbstractConfluenceExporter[ConfluenceClient]):
    """Exports pages from ``GET /wiki/api/v2/pages``.

    Each page includes ``spaceId`` and, when it has a page parent, ``parentId``.
    Deleted and trashed pages are never requested.
    """

    async def get_paginated_resources(
        self, options: PageExportOptions | None = None
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        selected = options or PageExportOptions()
        params: dict[str, Any] = {
            "status": (
                ["current", "archived"] if selected.include_archived else ["current"]
            ),
        }
        if selected.include_body:
            params["body-format"] = "markdown"
            params["limit"] = BODY_PAGE_SIZE
        if selected.space_ids:
            params["space-id"] = selected.space_ids

        async for batch in self.client.send_paginated_request("pages", params=params):
            yield [self._enrich(item) for item in batch]

    async def get_single_resource(self, resource_id: str) -> RAW_ITEM | None:
        payload = await self.client.send_api_request(
            f"pages/{resource_id}", missing_ok=True
        )
        return self._enrich(payload) if payload.get("id") else None

    def _enrich(self, item: dict[str, Any]) -> dict[str, Any]:
        return attach_web_url(self.client.site_url, item)
