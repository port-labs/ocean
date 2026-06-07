from typing import TYPE_CHECKING, Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from datadog.overrides import UserResourceConfig


class GetUserOptions(GetOptions["UserResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "UserResourceConfig", *, resource_id: str
    ) -> "GetUserOptions":
        return cls(resource_id=resource_id)


class UserExporter(PaginatedExporter[None], SingleResourceExporter[GetUserOptions]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/users/#list-all-users
        """
        url = f"{self.client.api_url}/api/v2/users"
        async for batch in self._paginate_by_page_param(url):
            yield batch

    async def get_resource(self, options: GetUserOptions) -> dict[str, Any] | None:
        """Get a single user by ID.
        Docs: https://docs.datadoghq.com/api/latest/users/#get-user-details
        """
        url = f"{self.client.api_url}/api/v2/users/{options.resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("data")

    async def get_resource_by_email(self, email: str) -> dict[str, Any] | None:
        """Get a single user by email.
        Docs: https://docs.datadoghq.com/api/latest/users/#list-all-users
        """
        url = f"{self.client.api_url}/api/v2/users"
        result = await self.client.send_api_request(
            url, params={"filter[email]": email}
        )
        users = result.get("data") or []
        return users[0] if users else None
