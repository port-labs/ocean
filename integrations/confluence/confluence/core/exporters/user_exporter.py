from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import RAW_ITEM

from confluence.clients.client import ConfluenceClient
from confluence.core.exporters.abstract_exporter import AbstractConfluenceExporter
from confluence.core.options import UserExportOptions

USER_SEARCH_PATH = "/wiki/rest/api/search/user"
USER_PAGE_SIZE = 100


class UserExporter(AbstractConfluenceExporter[ConfluenceClient]):
    """Exports users from ``GET /wiki/rest/api/search/user``.

    ``cql=type=user`` is the documented query for listing users. Confluence
    returns at most 10,000 users for that query. Pagination uses ``start``
    and ``limit``.
    """

    async def get_paginated_resources(
        self, options: UserExportOptions | None = None
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        selected = options or UserExportOptions()
        start = 0
        while True:
            payload = await self.client.send_api_request(
                USER_SEARCH_PATH,
                params={
                    "cql": "type=user",
                    "start": start,
                    "limit": USER_PAGE_SIZE,
                    "sitePermissionTypeFilter": selected.site_permission_type,
                },
            )
            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                break

            users = [
                self._user_from_result(item)
                for item in results
                if isinstance(item, dict) and isinstance(item.get("user"), dict)
            ]
            if users:
                yield users

            size = payload.get("size")
            total = payload.get("totalSize")
            page_size = size if isinstance(size, int) else len(results)
            start += page_size
            if page_size < USER_PAGE_SIZE or (
                isinstance(total, int) and start >= total
            ):
                break

    async def get_single_resource(self, resource_id: str) -> RAW_ITEM | None:
        payload = await self.client.send_api_request(
            USER_SEARCH_PATH,
            params={"cql": f'user="{resource_id}"', "limit": 1},
        )
        results = payload.get("results", [])
        if (
            not isinstance(results, list)
            or not results
            or not isinstance(results[0], dict)
        ):
            return None
        return self._user_from_result(results[0])

    def _user_from_result(self, result: dict[str, Any]) -> dict[str, Any]:
        user = result.get("user")
        enriched = dict(user) if isinstance(user, dict) else {}
        url = result.get("url")
        if isinstance(url, str) and url.startswith("/"):
            enriched["__webUrl"] = f"{self.client.site_url}/wiki{url}"
        return enriched
