"""User exporter for Okta integration."""

from typing import Any
from loguru import logger

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListUserOptions, GetUserOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class OktaUserExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta users."""

    async def _fetch_user(self, user_id: str) -> RAW_ITEM:
        response = await self.client.make_request(f"users/{user_id}")
        return response.json()

    async def _fetch_user_groups(self, user_id: str) -> list[dict[str, Any]]:
        response = await self.client.make_request(f"users/{user_id}/groups")
        return response.json() if response else []

    async def _fetch_user_apps(self, user_id: str) -> list[dict[str, Any]]:
        response = await self.client.make_request(f"users/{user_id}/appLinks")
        return response.json() if response else []

    def _iter_users(self, fields: str | None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {"fields": fields} if fields else None
        return self.client.send_paginated_request("users", params=params)

    async def get_resource(self, options: GetUserOptions) -> RAW_ITEM:
        """Get a single user resource.

        Args:
            options: Options for the request

        Returns:
            User data
        """
        user = await self._fetch_user(options.user_id)

        if options.include_groups:
            user["groups"] = await self._fetch_user_groups(options.user_id)

        if options.include_applications:
            user["applications"] = await self._fetch_user_apps(options.user_id)

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
        async for users in self._iter_users(options.fields):
            enriched_users = []
            for user in users:
                try:
                    # Get user's groups if requested
                    if options.include_groups:
                        user["groups"] = await self._fetch_user_groups(user["id"])

                    # Enrich applications strictly via API when requested
                    if options.include_applications:
                        user["applications"] = await self._fetch_user_apps(user["id"])

                    enriched_users.append(user)

                except Exception as e:
                    logger.warning(
                        f"Failed to enrich user {user.get('id', 'unknown')}: {e}"
                    )
                    # Still include the user without relations
                    enriched_users.append(user)

            yield enriched_users
