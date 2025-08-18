from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleProjectOptions, ListProjectOptions


class CheckmarxProjectExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One projects."""

    async def get_resource(self, options: SingleProjectOptions) -> RAW_ITEM:
        """Get a specific project by ID."""

        response = await self.client.send_api_request(
            f"/projects/{options['project_id']}"
        )
        logger.info(f"Fetched project with ID: {options['project_id']}")
        return response

    async def get_paginated_resources(
        self, options: ListProjectOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get projects from Checkmarx One.

        Args:
            limit: Maximum number of projects per page
            offset: Starting offset for pagination

        Yields:
            Batches of projects
        """

        async for projects in self.client.send_paginated_request(
            "/projects", "projects"
        ):
            logger.info(f"Fetched batch of {len(projects)} projects")
            yield projects
