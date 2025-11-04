"""Harbor Repositories Exporter."""

from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.clients.http.harbor_client import HarborClient
from harbor.core.options import (
    SingleRepositoryOptions,
    ListRepositoryOptions,
)
from harbor.helpers.utils import build_repository_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from port_ocean.utils.cache import cache_iterator_result
from loguru import logger


class HarborRepositoryExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor repositories."""

    async def get_resource(self, options: SingleRepositoryOptions) -> RAW_ITEM:
        """Get a single Harbor repository by project and name."""
        project_name = options["project_name"]
        repository_name = options["repository_name"]

        logger.info(f"Fetching Harbor repository: {project_name}/{repository_name}")

        response = await self.client.make_request(
            f"/projects/{project_name}/repositories/{repository_name}"
        )
        return response.json()

    @cache_iterator_result()
    async def get_paginated_resources(
        self, options: ListRepositoryOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor repositories with pagination and filtering."""
        logger.info("Starting Harbor repositories export")

        params = build_repository_params(options)
        project_name = options["project_name"]

        async for repositories_page in self.client.send_paginated_request(
            f"/projects/{project_name}/repositories", params=params
        ):
            for repository in repositories_page:
                repository["project_name"] = project_name

            logger.info(f"Fetched {len(repositories_page)} repositories")
            yield repositories_page
