import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from datadog.overrides import RoleResourceConfig


class ListRoleOptions(ListOptions["RoleResourceConfig"]):
    enrich_with_users: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "RoleResourceConfig"
    ) -> "ListRoleOptions":
        return cls(enrich_with_users=resource_config.selector.enrich_with_users)


class GetRoleOptions(GetOptions["RoleResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "RoleResourceConfig", *, resource_id: str
    ) -> "GetRoleOptions":
        return cls(resource_id=resource_id)


class RoleExporter(PaginatedExporter[None], SingleResourceExporter[GetRoleOptions]):
    async def get_paginated_resources(
        self, options: ListRoleOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get roles from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/roles/#list-roles
        """
        url = f"{self.client.api_url}/api/v2/roles"
        async for batch in self._paginate_by_page_param(url):
            if options.enrich_with_users:
                batch = await self.enrich_role_with_users(batch)

            yield batch

    async def get_resource(self, options: GetRoleOptions) -> dict[str, Any] | None:
        """Get a single role by ID.
        Docs: https://docs.datadoghq.com/api/latest/roles/#get-a-role
        """
        url = f"{self.client.api_url}/api/v2/roles/{options.resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("data")

    async def enrich_role_with_users(
        self, role_batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching related users for {len(role_batch)} roles")

        related_user_tasks = [
            self._fetch_users_for_role(role["id"]) for role in role_batch
        ]
        results = await asyncio.gather(*related_user_tasks, return_exceptions=True)

        for role, users in zip(role_batch, results):
            if isinstance(users, Exception):
                logger.warning(
                    f"Error {users} occurred while fetching related users for role {role.get('attributes', {}).get('name')}"
                )
                role["__users"] = []
                continue
            role["__users"] = users
        return role_batch

    async def _fetch_users_for_role(self, role_id: str) -> list[dict[str, Any]]:
        """Get roles for specified Datadog role.
        Docs: https://docs.datadoghq.com/api/latest/roles/get-all-users-of-a-role/
        """
        url = f"{self.client.api_url}/api/v2/roles/{role_id}/users"
        users: list[dict[str, Any]] = []
        async for user_batch in self._paginate_by_page_param(url):
            users.extend(user_batch)

        return users
