import asyncio
from itertools import batched
from typing import Any, Dict, cast

from loguru import logger

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListUserOptions, GetUserOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class OktaUserExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta users."""

    SUB_BATCH_SIZE: int = 10

    async def _fetch_user(self, user_id: str) -> RAW_ITEM:
        return cast(RAW_ITEM, await self.client.send_api_request(f"users/{user_id}"))

    async def _fetch_user_groups(self, user_id: str) -> list[dict[str, Any]]:
        all_groups: list[dict[str, Any]] = []
        async for groups in self.client.send_paginated_request(
            f"users/{user_id}/groups"
        ):
            all_groups.extend(groups)
        return all_groups

    async def _fetch_user_apps(self, user_id: str) -> list[RAW_ITEM]:
        all_apps: list[RAW_ITEM] = []
        async for apps in self.client.send_paginated_request(
            f"users/{user_id}/appLinks"
        ):
            all_apps.extend(apps)
        return all_apps

    async def _fetch_enrichments(
        self, user_id: str, include_groups: bool, include_applications: bool
    ) -> dict[str, Any]:
        enrichments: dict[str, Any] = {}
        if include_groups:
            enrichments["groups"] = await self._fetch_user_groups(user_id)
        if include_applications:
            enrichments["applications"] = await self._fetch_user_apps(user_id)
        return enrichments

    async def _enrich_single_user(
        self,
        user: dict[str, Any],
        options: ListUserOptions,
    ) -> dict[str, Any]:
        try:
            enrichments = await self._fetch_enrichments(
                user["id"],
                bool(options.get("include_groups")),
                bool(options.get("include_applications")),
            )
            if enrichments:
                user |= enrichments
        except Exception as exc:
            logger.warning(f"Failed to enrich user {user.get('id', 'unknown')}: {exc}")
        return user

    async def get_resource(self, options: GetUserOptions) -> RAW_ITEM:
        """Get a single user resource."""
        user_task = self._fetch_user(options["user_id"])
        enrich_task = self._fetch_enrichments(
            options["user_id"],
            bool(options.get("include_groups")),
            bool(options.get("include_applications")),
        )
        user, enrichments = await asyncio.gather(user_task, enrich_task)
        if enrichments:
            user |= enrichments

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
        params: Dict[str, Any] = {"fields": options["fields"]}

        async for users in self.client.send_paginated_request("users", params):
            for batched_users in batched(users, self.SUB_BATCH_SIZE):
                tasks = [
                    asyncio.create_task(self._enrich_single_user(user, options))
                    for user in batched_users
                ]

                results = await asyncio.gather(*tasks)
                yield results
