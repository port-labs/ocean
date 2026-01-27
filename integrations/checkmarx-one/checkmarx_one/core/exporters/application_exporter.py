from typing import Any
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
        params: dict[str, Any] = {}
        if options.get("tag_keys"):
            params["tag-keys"] = options["tag_keys"]
        if options.get("tag_values"):
            params["tag-values"] = options["tag_values"]
        if options.get("name"):
            params["name"] = options["name"]
        async for applications in self.client.send_paginated_request(
            "/applications", "applications", params=params
        ):
            logger.info(f"Fetched batch of {len(applications)} applications")
            yield applications
