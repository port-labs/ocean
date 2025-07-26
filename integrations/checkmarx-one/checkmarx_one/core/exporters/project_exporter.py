from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import ListProjectOptions, SingleProjectOptions


class CheckmarxProjectExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One projects."""

    async def get_resource[
        ExporterOptionsT: SingleProjectOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """Get a single project by ID."""
        project_id = options["project_id"]
        project = await self.client.get_project_by_id(project_id)
        logger.info(f"Fetched project with ID: {project_id}")
        return project

    async def get_paginated_resources[
        ExporterOptionsT: ListProjectOptions
    ](self, options: ExporterOptionsT | None = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all projects with pagination."""
        if options is None:
            options = {}

        limit = options.get("limit")
        offset = options.get("offset")

        async for projects_batch in self.client.get_projects(limit=limit, offset=offset):
            logger.info(f"Fetched batch of {len(projects_batch)} projects")
            yield projects_batch
