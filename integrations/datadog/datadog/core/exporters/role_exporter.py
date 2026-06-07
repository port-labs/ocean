from typing import TYPE_CHECKING, Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from datadog.overrides import RoleResourceConfig


class GetRoleOptions(GetOptions["RoleResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "RoleResourceConfig", *, resource_id: str
    ) -> "GetRoleOptions":
        return cls(resource_id=resource_id)


class RoleExporter(PaginatedExporter[None], SingleResourceExporter[GetRoleOptions]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get roles from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/roles/#list-roles
        """
        url = f"{self.client.api_url}/api/v2/roles"
        async for batch in self._paginate_by_page_param(url):
            yield batch

    async def get_resource(self, options: GetRoleOptions) -> dict[str, Any] | None:
        """Get a single role by ID.
        Docs: https://docs.datadoghq.com/api/latest/roles/#get-a-role
        """
        url = f"{self.client.api_url}/api/v2/roles/{options.resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("data")
