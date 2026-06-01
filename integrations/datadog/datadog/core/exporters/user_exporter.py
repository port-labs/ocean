from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import PaginatedExporter


class UserExporter(PaginatedExporter[None]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/users/#list-all-users
        """
        url = f"{self.client.api_url}/api/v2/users"
        async for batch in self._paginate_by_page_param(url):
            yield batch
