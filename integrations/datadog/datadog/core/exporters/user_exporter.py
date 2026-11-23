from datetime import datetime
from typing import TYPE_CHECKING, Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from datadog.incremental import (
    CHANGED_USERS_AUDIT_QUERY,
    ROLES_API_PATH_PREFIX,
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

    async def get_changed_users(
        self, incremental_cursor: datetime
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users created or modified since ``incremental_cursor``, found through audit events.
        Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
        """
        user_ids = await self._changed_asset_ids(
            CHANGED_USERS_AUDIT_QUERY,
            incremental_cursor,
            excluded_path_prefix=ROLES_API_PATH_PREFIX,
        )

        async for users in self._get_existing_resources(
            GetUserOptions(resource_id=user_id) for user_id in user_ids
        ):
            yield users

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
        result = await self.client.send_api_request(url, params={"filter": email})
        users = result.get("data") or []
        return users[0] if users else None
