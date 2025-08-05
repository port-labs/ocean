from collections.abc import AsyncGenerator
from typing import Any, Dict
from loguru import logger

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


class CheckmarxProjectExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One projects."""

    async def get_resource(self, options: Dict[str, Any]) -> dict[str, Any]:
        """Get a specific project by ID."""
        response = await self.client.send_api_request(
            f"/projects/{options['project_id']}"
        )
        logger.info(f"Fetched project with ID: {options['project_id']}")
        return response

    async def get_paginated_resources(
        self,
        options: Dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get projects from Checkmarx One.

        Args:
            limit: Maximum number of projects per page
            offset: Starting offset for pagination

        Yields:
            Batches of projects
        """
        params = {}
        limit = options.get("limit")
        offset = options.get("offset")
        if limit is not None:
            params["limit"] = limit
        if offset is not None and offset > 0:
            params["offset"] = offset

        async for projects in self.client.send_paginated_request(
            "/projects", "projects", params
        ):
            logger.info(f"Fetched batch of {len(projects)} projects")
            yield projects
