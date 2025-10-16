"""Harbor Projects Exporter."""

from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.clients.http.harbor_client import HarborClient
from harbor.core.options import SingleProjectOptions, ListProjectOptions
from harbor.helpers.utils import build_project_params
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger


class HarborProjectExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor projects."""

    async def get_resource(self, options: SingleProjectOptions) -> RAW_ITEM:
        """Get a single Harbor project by name."""
        project_name = options["project_name"]

        logger.info(f"Fetching Harbor project: {project_name}")

        response = await self.client.make_request(f"/projects/{project_name}")
        return response.json()

    async def get_paginated_resources(
        self, options: ListProjectOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all Harbor projects with pagination and filtering."""
        logger.info("Starting Harbor projects export")

        # Build query parameters using utility function
        params = build_project_params(options)

        async for projects_page in self.client.send_paginated_request(
            "/projects", params=params
        ):
            logger.debug(f"Fetched {len(projects_page)} projects")
            yield projects_page
