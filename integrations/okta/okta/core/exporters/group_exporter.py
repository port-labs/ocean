"""Group exporter for Okta integration."""

import logging

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListGroupOptions, GetGroupOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

logger = logging.getLogger(__name__)


class OktaGroupExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta groups."""

    async def get_resource(self, options: GetGroupOptions) -> RAW_ITEM:
        """Get a single group resource.

        Args:
            options: Options for the request

        Returns:
            Group data
        """
        group = await self.client.get_group(options.group_id)

        if options.include_members:
            group["members"] = await self.client.get_group_members(options.group_id)

        return group

    def get_paginated_resources(
        self, options: ListGroupOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get groups with pagination support.

        Args:
            options: Options for the request

        Yields:
            List of groups from each page
        """
        return self._get_groups_with_relations(options)

    async def _get_groups_with_relations(
        self, options: ListGroupOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get groups with their related data (members).

        Args:
            options: Options for the request

        Yields:
            List of groups with enriched data
        """
        async for groups in self.client.get_groups(
            search=options.search,
            filter_query=options.filter_query,
            limit=options.limit,
        ):
            enriched_groups = []
            for group in groups:
                try:
                    # Get group members if requested
                    if options.include_members:
                        group_members = await self.client.get_group_members(group["id"])
                        group["members"] = group_members

                    enriched_groups.append(group)

                except Exception as e:
                    logger.warning(
                        f"Failed to enrich group {group.get('id', 'unknown')}: {e}"
                    )
                    # Still include the group without relations
                    enriched_groups.append(group)

            yield enriched_groups
