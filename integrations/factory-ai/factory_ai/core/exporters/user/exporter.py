from __future__ import annotations

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from factory_ai.core.exporters.abstract_exporter import AbstractFactoryExporter
from factory_ai.core.exporters.user.models import (
    GetUserOptions,
    ListUserOptions,
    ListUsersResponse,
)

_USERS_PATH = "/api/v0/organization/users"


class UserExporter(AbstractFactoryExporter[ListUserOptions, GetUserOptions]):
    async def get_paginated_resources(
        self, options: ListUserOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor: str | None = None
        while True:
            params = options.to_query_params()
            if cursor:
                params["cursor"] = cursor

            response = await self.client.get(
                _USERS_PATH,
                ListUsersResponse,
                params=params or None,
            )
            logger.debug(
                f"Fetched Factory users batch with {len(response.users)} records"
            )
            yield [user.to_raw_item() for user in response.users]

            if not response.pagination.has_more or not response.pagination.next_cursor:
                break
            cursor = response.pagination.next_cursor

    async def get_resource(self, options: GetUserOptions) -> RAW_ITEM | None:
        # Organization users have no get-by-id endpoint; scan list pages.
        async for batch in self.get_paginated_resources(ListUserOptions()):
            for item in batch:
                if item.get("id") == options.user_id:
                    return item
        return None
