"""Project exporter for Harbor integration."""

from typing import Optional, cast

from loguru import logger

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.abstract_exporter import AbstractHarborExporter
from harbor.core.options import ListProjectOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class HarborProjectExporter(AbstractHarborExporter[HarborClient]):
    """Exporter for Harbor projects."""

    async def get_resource(self, project_id: str) -> RAW_ITEM:
        """Get a single project resource."""
        return cast(
            RAW_ITEM,
            await self.client.send_api_request(f"projects/{project_id}"),
        )

    async def get_paginated_resources(
        self, options: Optional[ListProjectOptions] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get projects with pagination support.

        Args:
            options: Options for filtering projects

        Yields:
            List of projects from each page
        """
        params = {}
        if options:
            public = options.get("public")
            if public is not None:
                params["public"] = str(public).lower()

        logger.info(f"Fetching projects from Harbor with params: {params}")

        async for response in self.client.send_paginated_request("projects", params):
            projects = self._extract_items_from_response(response)
            if projects:
                logger.debug(f"Fetched {len(projects)} projects")
                yield projects

