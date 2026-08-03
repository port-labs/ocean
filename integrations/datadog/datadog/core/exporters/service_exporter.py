from typing import TYPE_CHECKING, Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from datadog.overrides import ServiceResourceConfig


class GetServiceOptions(GetOptions["ServiceResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "ServiceResourceConfig", *, resource_id: str
    ) -> "GetServiceOptions":
        return cls(resource_id=resource_id)


class ServiceExporter(
    PaginatedExporter[None], SingleResourceExporter[GetServiceOptions]
):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get services from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/service-definition/#get-all-service-definitions
        """
        url = f"{self.client.api_url}/api/v2/services/definitions"
        async for batch in self._paginate_by_page_param(
            url, extra_params={"schema_version": "v2.2"}
        ):
            yield batch

    async def get_resource(self, options: GetServiceOptions) -> dict[str, Any] | None:
        """Get a single service by ID."""
        url = f"{self.client.api_url}/api/v2/services/definitions/{options.resource_id}"
        return await self.client.send_api_request(url)
