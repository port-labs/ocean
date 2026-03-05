"""Deployment exporter for Vercel integration."""

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from vercel.core.exporters.abstract_exporter import AbstractVercelExporter


class DeploymentExporter(AbstractVercelExporter):
    """Exporter for Vercel deployments."""

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get paginated deployments from the API.

        Iterates through all projects and fetches deployments for each,
        ensuring projectId is attached for relation resolution.
        """
        async for project in self.client.get_all_projects_flat():
            project_id = project["id"]
            project_name = project.get("name", project_id)

            async for deployments_batch in self.client.get_deployments(
                project_id=project_id
            ):
                # Ensure each deployment knows which project it belongs to
                for deployment in deployments_batch:
                    deployment.setdefault("name", project_name)
                    deployment["projectId"] = project_id

                logger.info(
                    f"Yielding {len(deployments_batch)} deployment(s) for project {project_name}"
                )
                yield deployments_batch
