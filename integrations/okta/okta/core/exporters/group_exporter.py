import logging

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

logger = logging.getLogger(__name__)


class OktaGroupExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta groups."""

    async def get_resource(self, group_id: str) -> RAW_ITEM:
        """Get a single group resource.

        Args:
            group_id: The ID of the group to retrieve

        Returns:
            Group data
        """
        return await self.client.get_group(group_id)

    async def get_paginated_resources(
        self, options: object
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get groups with pagination support.

        Args:
            None

        Yields:
            List of groups from each page
        """
        async for groups in self.client.get_groups():
            yield groups
