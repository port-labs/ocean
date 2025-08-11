from typing import Any, cast
from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from checkmarx_one.core.options import ListProjectOptions, SingleProjectOptions


class CheckmarxProjectExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One projects."""

    async def get_resource[
        SingleProjectOptionsT: SingleProjectOptions
    ](self, options: SingleProjectOptionsT) -> RAW_ITEM:
        """Get a specific project by ID."""
        response = await self.client.send_api_request(
            f"/projects/{options['project_id']}"
        )
        logger.info(f"Fetched project with ID: {options['project_id']}")
        return response

    async def get_paginated_resources[
        ListProjectOptionsT: ListProjectOptions
    ](self, options: ListProjectOptionsT,) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get projects from Checkmarx One.

        Args:
            limit: Maximum number of projects per page
            offset: Starting offset for pagination

        Yields:
            Batches of projects
        """
        params: dict[str, Any] = {}
        limit = options.get("limit")
        offset = options.get("offset")
        if limit is not None:
            params["limit"] = limit
        if offset is not None and cast(int, offset) > 0:
            params["offset"] = offset

        async for projects in self.client.send_paginated_request(
            "/projects", "projects", params
        ):
            logger.info(f"Fetched batch of {len(projects)} projects")
            yield projects
