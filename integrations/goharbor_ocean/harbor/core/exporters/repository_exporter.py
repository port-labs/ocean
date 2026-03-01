"""Harbor Repositories Exporter."""

from typing import cast

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListRepositoryOptions


class HarborRepositoryExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor repositories."""

    async def get_resource(self, project_name: str, repository_name: str) -> RAW_ITEM:
        """Get a single Harbor repository.

        Args:
            project_name: Name of the project
            repository_name: Name of the repository

        Returns:
            Repository data
        """
        logger.info(f"Fetching Harbor repository: {project_name}/{repository_name}")

        return cast(
            RAW_ITEM, await self.client.send_api_request(f"/projects/{project_name}/repositories/{repository_name}")
        )

    async def get_paginated_resources(self, options: ListRepositoryOptions) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor repositories for a project with pagination.

        Args:
            options: Options including project_name and filters

        Yields:
            Batches of repositories
        """
        project_name = options["project_name"]

        logger.info(f"Starting Harbor repositories export for project: {project_name}")

        params = {}

        if q := options.get("q"):
            params["q"] = q

        if sort := options.get("sort"):
            params["sort"] = sort

        endpoint = f"/projects/{project_name}/repositories"

        async for repositories_page in self.client.send_paginated_request(endpoint, params=params):
            logger.debug(f"Fetched {len(repositories_page)} repositories from {project_name}")
            yield repositories_page
