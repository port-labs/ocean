from collections.abc import AsyncGenerator
from typing import Any, Optional
from loguru import logger

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


class CheckmarxProjectExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One projects."""

    async def get_project_by_id(self, project_id: str) -> dict[str, Any]:
        """Get a specific project by ID."""
        response = await self.client._send_api_request(f"/projects/{project_id}")
        logger.info(f"Fetched project with ID: {project_id}")
        return response

    async def get_projects(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        async for projects in self.client._get_paginated_resources(
            "/projects", "projects", params
        ):
            logger.info(f"Fetched batch of {len(projects)} projects")
            yield projects
