from typing import Any, Optional, AsyncGenerator, Mapping, cast
from loguru import logger

from port_ocean.core.ocean_types import RAW_ITEM, ASYNC_GENERATOR_RESYNC_TYPE
from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter


class CheckmarxProjectExporter(AbstractCheckmarxExporter):
    """Exporter for Checkmarx One projects."""

    async def get_resource(self, options: Optional[Mapping[str, Any]]) -> RAW_ITEM:
        """Get a specific project by ID."""
        assert options is not None and "project_id" in options
        response = await self.client.send_api_request(
            f"/projects/{options['project_id']}"
        )
        logger.info(f"Fetched project with ID: {options['project_id']}")
        return response

    def get_paginated_resources(
        self, options: Optional[Mapping[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """
        Get projects from Checkmarx One.

        Args:
            limit: Maximum number of projects per page
            offset: Starting offset for pagination

        Yields:
            Batches of projects
        """
        params: dict[str, Any] = {}
        limit = (options or {}).get("limit")
        offset = (options or {}).get("offset")
        if limit is not None:
            params["limit"] = limit
        if offset is not None and cast(int, offset) > 0:
            params["offset"] = offset

        async def _gen() -> AsyncGenerator[list[dict[str, Any]], None]:
            async for projects in self.client.send_paginated_request(
                "/projects", "projects", params
            ):
                logger.info(f"Fetched batch of {len(projects)} projects")
                yield projects

        return _gen()
