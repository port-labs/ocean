from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base import PaginatedExporter


class HostExporter(PaginatedExporter[None]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get hosts from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/hosts/#get-all-hosts-for-your-organization
        """
        url = f"{self.client.api_url}/api/v1/hosts"
        async for batch in self._paginate_by_offset(
            url,
            data_key="host_list",
            offset_param="start",
            size_param="count",
        ):
            yield batch
