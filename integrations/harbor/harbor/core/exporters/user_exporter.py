"""Harbor Users Exporter."""

from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.clients.http.harbor_client import HarborClient
from harbor.core.options import SingleUserOptions, ListUserOptions
from harbor.helpers.utils import build_user_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger


class HarborUserExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor users."""

    async def get_resource(self, options: SingleUserOptions) -> RAW_ITEM:
        """Get a single Harbor user by ID."""
        user_id = options["user_id"]

        logger.info(f"Fetching Harbor user: {user_id}")

        response = await self.client.make_request(f"/users/{user_id}")
        return response.json()

    async def get_paginated_resources(
        self, options: ListUserOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor users with pagination and filtering."""
        logger.info("Starting Harbor users export")

        params = build_user_params(options)

        async for users_page in self.client.send_paginated_request(
            "/users", params=params
        ):
            logger.debug(f"Fetched {len(users_page)} users")
            yield users_page
