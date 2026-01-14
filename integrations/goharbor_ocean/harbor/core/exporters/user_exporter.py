"""Harbor Users Exporter."""

from typing import cast

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListUserOptions


class HarborUserExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor users."""

    async def get_resource(self, user_id: int) -> RAW_ITEM:
        """Get a single Harbor user by ID.

        Args:
            user_id: ID of the user to fetch

        Returns:
            User data
        """
        logger.info(f"Fetching Harbor user: {user_id}")

        return cast(RAW_ITEM, await self.client.send_api_request(f"/users/{user_id}"))

    async def get_paginated_resources(self, options: ListUserOptions) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor users with pagination and filtering.

        Args:
            options: Filtering options for users

        Yields:
            Batches of users
        """
        logger.info("Starting Harbor users export")

        params = {}

        if q := options.get("q"):
            params["q"] = q

        if sort := options.get("sort"):
            params["sort"] = sort

        async for users_page in self.client.send_paginated_request("/users", params=params):
            logger.debug(f"Fetched {len(users_page)} users")
            yield users_page
