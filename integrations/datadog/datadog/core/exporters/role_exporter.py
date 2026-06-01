from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import PaginatedExporter


class RoleExporter(PaginatedExporter[None]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get roles from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/roles/#list-roles
        """
        url = f"{self.client.api_url}/api/v2/roles"
        async for batch in self._paginate_by_page_param(url):
            yield batch
