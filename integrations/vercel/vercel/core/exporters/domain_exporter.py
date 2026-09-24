"""Domain exporter for Vercel integration."""

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.core.exporters.abstract_exporter import AbstractVercelExporter


class DomainExporter(AbstractVercelExporter):
    """Exporter for Vercel domains."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get paginated domains from the API.

        Iterates through all projects and fetches domains for each.
        """
        async for project in self.client.get_all_projects_flat():
            project_id = project["id"]

            async for domains_batch in self.client.get_project_domains(project_id):
                logger.info(
                    f"Yielding {len(domains_batch)} domain(s) for project {project_id}"
                )
                yield domains_batch
