"""Repository exporter for Harbor integration."""

from typing import Optional, cast

from loguru import logger

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListRepositoryOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class HarborRepositoryExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor repositories."""

    async def get_resource(self, repository_name: str) -> RAW_ITEM:
        """Get a single repository resource."""
        return cast(
            RAW_ITEM,
            await self.client.send_api_request(f"repositories/{repository_name}"),
        )

    async def get_paginated_resources(
        self, options: Optional[ListRepositoryOptions] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get repositories with pagination support.

        Args:
            options: Options for filtering repositories

        Yields:
            List of repositories from each page
        """
        params = {}

        logger.info("Fetching repositories from Harbor")

        async for response in self.client.send_paginated_request(
            "repositories", params
        ):
            repositories = self._extract_items_from_response(response)
            if repositories:
                logger.debug(f"Fetched {len(repositories)} repositories")
                yield repositories

