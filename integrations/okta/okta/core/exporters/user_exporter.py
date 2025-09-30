"""User exporter for Okta integration."""

import asyncio
from typing import Any, Dict, List, cast
from loguru import logger

from okta.clients.http.client import OktaClient
from okta.core.exporters.abstract_exporter import AbstractOktaExporter
from okta.core.options import ListUserOptions, GetUserOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class OktaUserExporter(AbstractOktaExporter[OktaClient]):
    """Exporter for Okta users."""

    ENRICH_CONCURRENCY: int = 10

    async def _fetch_user(self, user_id: str) -> RAW_ITEM:
        return cast(RAW_ITEM, await self.client.send_api_request(f"users/{user_id}"))

    async def _fetch_user_groups(self, user_id: str) -> list[dict[str, Any]]:
        return cast(
            List[RAW_ITEM],
            await self.client.send_api_request(f"users/{user_id}/groups"),
        )

    async def _fetch_user_apps(self, user_id: str) -> list[RAW_ITEM]:
        return cast(
            List[RAW_ITEM],
            await self.client.send_api_request(f"users/{user_id}/appLinks"),
        )

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
        semaphore: asyncio.Semaphore,
        options: ListUserOptions,
    ) -> dict[str, Any]:
        async with semaphore:
            try:
                enrichments = await self._fetch_enrichments(
                    user["id"],
                    bool(options.get("include_groups")),
                    bool(options.get("include_applications")),
                )
                if enrichments:
                    user |= enrichments
            except Exception as exc:
                logger.warning(
                    f"Failed to enrich user {user.get('id', 'unknown')}: {exc}"
                )
            return user

    async def get_resource(self, options: GetUserOptions) -> RAW_ITEM:
        """Get a single user resource.

        Args:
            options: Options for the request

        Returns:
            User data
        """
        user = await self._fetch_user(options["user_id"])
        enrichments = await self._fetch_enrichments(
            options["user_id"],
            bool(options.get("include_groups")),
            bool(options.get("include_applications")),
        )
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
            semaphore = asyncio.Semaphore(self.ENRICH_CONCURRENCY)
            tasks = [
                asyncio.create_task(self._enrich_single_user(user, semaphore, options))
                for user in users
            ]
            enriched_users = await asyncio.gather(*tasks)
            yield list(enriched_users)
