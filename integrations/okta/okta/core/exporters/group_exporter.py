from typing import Optional

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListGroupOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class OktaGroupExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta groups."""

    async def _fetch_group(self, group_id: str) -> RAW_ITEM:
        response = await self.client.make_request(f"groups/{group_id}")
        return response.json()

    async def get_resource(self, group_id: str) -> RAW_ITEM:
        """Get a single group resource.

        Args:
            group_id: The ID of the group to retrieve

        Returns:
            Group data
        """
        return await self._fetch_group(group_id)

    async def get_paginated_resources(
        self, options: Optional[ListGroupOptions] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get groups with pagination support.

        Args:
            None

        Yields:
            List of groups from each page
        """
        async for groups in self.client.send_paginated_request("groups"):
            yield groups
