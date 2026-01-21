from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import SingleApplicationOptions, ListApplicationOptions


class CheckmarxApplicationExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One applications."""

    async def get_resource(self, options: SingleApplicationOptions) -> RAW_ITEM:
        """Get a specific application by ID."""
        response = await self.client.send_api_request(
            f"/applications/{options['application_id']}"
        )
        logger.info(f"Fetched application with ID: {options['application_id']}")
        return response

    async def get_paginated_resources(
        self, options: ListApplicationOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get applications from Checkmarx One.

        Yields:
            Batches of applications
        """
        async for applications in self.client.send_paginated_request(
            "/applications", "applications"
        ):
            logger.info(f"Fetched batch of {len(applications)} applications")
            yield applications

    async def get_application_projects(
        self, application_id: str
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get projects belonging to a specific application.

        Args:
            application_id: The ID of the application

        Yields:
            Batches of projects belonging to the application
        """
        async for projects in self.client.send_paginated_request(
            f"/applications/{application_id}/projects", "projects"
        ):
            logger.info(
                f"Fetched batch of {len(projects)} projects for application {application_id}"
            )
            yield projects
