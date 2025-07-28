from typing import Any, AsyncIterator, cast
from loguru import logger
from port_ocean.core.ocean_types import RAW_ITEM

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

    def get_paginated_resources[
        ExporterOptionsT: ListProjectOptions
    ](self, options: ExporterOptionsT | None = None) -> AsyncIterator[
        list[dict[str, Any]]
    ]:
        """Get all projects with pagination."""
        if options is None:
            options = cast(ExporterOptionsT, {})

        limit = options.get("limit")
        offset = options.get("offset")

        async def _get_projects() -> AsyncIterator[list[dict[str, Any]]]:
            async for projects_batch in self.client.get_projects(
                limit=cast(int | None, limit), offset=cast(int | None, offset)
            ):
                logger.info(f"Fetched batch of {len(projects_batch)} projects")
                yield projects_batch

        return _get_projects()
