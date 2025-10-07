from typing import Optional, cast

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListGroupOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class OktaGroupExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta groups."""

    async def get_resource(self, group_id: str) -> RAW_ITEM:
        """Get a single group resource.

        Args:
            group_id: The ID of the group to retrieve

        Returns:
            Group data
        """
        return cast(RAW_ITEM, await self.client.send_api_request(f"groups/{group_id}"))

    async def get_paginated_resources(
        self, options: Optional[ListGroupOptions] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get groups with pagination support.

        Yields:
            List of groups from each page
        """
        async for groups in self.client.send_paginated_request("groups"):
            yield groups
