"""Harbor Projects Exporter."""

from typing import cast

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListProjectOptions


class HarborProjectExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor projects."""

    async def get_resource(self, project_name: str) -> RAW_ITEM:
        """Get a single Harbor project by name.

        Args:
            project_name: Name of the project to fetch

        Returns:
            Project data
        """
        logger.info(f"Fetching Harbor project: {project_name}")

        return cast(RAW_ITEM, await self.client.send_api_request(f"/projects/{project_name}"))

    @cache_iterator_result()
    async def get_paginated_resources(self, options: ListProjectOptions) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor projects with pagination and filtering.

        Args:
            options: Filtering options for projects

        Yields:
            Batches of projects
        """
        logger.info("Starting Harbor projects export")

        params = {}

        if q := options.get("q"):
            params["q"] = q

        if sort := options.get("sort"):
            params["sort"] = sort

        async for projects_page in self.client.send_paginated_request("/projects", params=params):
            logger.debug(f"Fetched {len(projects_page)} projects")
            yield projects_page
