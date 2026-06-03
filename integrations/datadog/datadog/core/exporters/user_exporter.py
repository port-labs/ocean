from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from typing import Any

from datadog.core.exporters.base_exporter import PaginatedExporter, SingleResourceExporter


class UserExporter(PaginatedExporter[None], SingleResourceExporter[str]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/users/#list-all-users
        """
        url = f"{self.client.api_url}/api/v2/users"
        async for batch in self._paginate_by_page_param(url):
            yield batch

    async def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        """Get a single user by ID.
        Docs: https://docs.datadoghq.com/api/latest/users/#get-user-details
        """
        url = f"{self.client.api_url}/api/v2/users/{resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("data")
