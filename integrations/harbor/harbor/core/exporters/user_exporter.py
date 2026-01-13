"""User exporter for Harbor integration."""

from typing import Optional, cast

from loguru import logger

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListUserOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class HarborUserExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor users."""

    async def get_resource(self, user_id: str) -> RAW_ITEM:
        """Get a single user resource.

        Args:
            user_id: The ID of the user to retrieve

        Returns:
            User data
        """
        return cast(
            RAW_ITEM,
            await self.client.send_api_request(f"users/{user_id}"),
        )

    async def get_paginated_resources(
        self, options: Optional[ListUserOptions] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users with pagination support.

        Args:
            options: Options for filtering users

        Yields:
            List of users from each page
        """
        params = {}

        logger.info("Fetching users from Harbor")

        async for response in self.client.send_paginated_request("users", params):
            users = self._extract_items_from_response(response)
            if users:
                logger.debug(f"Fetched {len(users)} users")
                yield users

