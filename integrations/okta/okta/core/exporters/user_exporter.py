"""User exporter for Okta integration."""

import logging

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListUserOptions, GetUserOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

logger = logging.getLogger(__name__)


class OktaUserExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta users."""

    async def get_resource(self, options: GetUserOptions) -> RAW_ITEM:
        """Get a single user resource.

        Args:
            options: Options for the request

        Returns:
            User data
        """
        user = await self.client.get_user(options.user_id)

        if options.include_groups:
            user["groups"] = await self.client.get_user_groups(options.user_id)

        if options.include_applications:
            user["applications"] = await self.client.get_user_apps(options.user_id)

        return user

    async def get_paginated_resources(
        self, options: ListUserOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get users with pagination support.

        Args:
            options: Options for the request

        Yields:
            List of users from each page
        """
        async for users in self.client.get_users(
            fields=options.fields,
        ):
            enriched_users = []
            for user in users:
                try:
                    # Get user's groups if requested
                    if options.include_groups:
                        user_groups = await self.client.get_user_groups(user["id"])
                        user["groups"] = user_groups

                    # Enrich applications strictly via API when requested
                    if options.include_applications:
                        user_apps = await self.client.get_user_apps(user["id"])
                        user["applications"] = user_apps

                    enriched_users.append(user)

                except Exception as e:
                    logger.warning(
                        f"Failed to enrich user {user.get('id', 'unknown')}: {e}"
                    )
                    # Still include the user without relations
                    enriched_users.append(user)

            yield enriched_users
