from typing import Any, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.clients.http.clickup_client import ClickUpClient
from clickup.core.exporters.abstract_exporter import AbstractClickUpExporter


class ListExporter(AbstractClickUpExporter[ClickUpClient]):
    """Exporter for ClickUp Lists.

    Lists can exist:
    1. Inside folders: GET /v2/folder/{folder_id}/list
    2. Directly in spaces (folderless): GET /v2/space/{space_id}/list

    Reference:
    - https://developer.clickup.com/reference/getlists
    - https://developer.clickup.com/reference/getfolderlesslists
    """

    async def get_paginated_resources(
        self,
        options: Optional[dict[str, Any]] = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all lists across all folders and spaces.

        Args:
            options: Optional dict with:
                - folder_id: Fetch lists for specific folder only
                - space_id: Fetch folderless lists for specific space only
                - archived: Include archived lists (default: False)
        """
        options = options or {}
        folder_id = options.get("folder_id")
        space_id = options.get("space_id")
        include_archived = options.get("archived", False)

        params = {"archived": str(include_archived).lower()}

        if folder_id:
            async for batch in self._get_lists_from_folder(folder_id, params):
                yield batch
        elif space_id:
            async for batch in self._get_folderless_lists(space_id, params):
                yield batch
        else:
            async for batch in self._get_all_lists(params, include_archived):
                yield batch

    async def _get_lists_from_folder(
        self, folder_id: str, params: dict[str, Any]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get lists from a specific folder."""
        logger.info(f"Fetching lists for folder {folder_id}")

        response = await self.client.send_api_request(
            f"/v2/folder/{folder_id}/list",
            params=params,
        )

        if not response:
            return

        lists = response.get("lists", [])
        if lists:
            for lst in lists:
                lst["__folder_id"] = folder_id
            logger.info(f"Fetched {len(lists)} lists from folder {folder_id}")
            yield lists

    async def _get_folderless_lists(
        self, space_id: str, params: dict[str, Any]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get folderless lists from a specific space."""
        logger.info(f"Fetching folderless lists for space {space_id}")

        response = await self.client.send_api_request(
            f"/v2/space/{space_id}/list",
            params=params,
        )

        if not response:
            return

        lists = response.get("lists", [])
        if lists:
            for lst in lists:
                lst["__space_id"] = space_id
                lst["__folder_id"] = None
            logger.info(f"Fetched {len(lists)} folderless lists from space {space_id}")
            yield lists

    async def _get_all_lists(
        self, params: dict[str, Any], include_archived: bool
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all lists from all workspaces, spaces, and folders."""
        workspaces_response = await self.client.send_api_request("/v2/team")

        for team in workspaces_response.get("teams", []):
            ws_id = str(team["id"])

            spaces_response = await self.client.send_api_request(
                f"/v2/team/{ws_id}/space",
                params={"archived": str(include_archived).lower()},
            )

            for space in spaces_response.get("spaces", []):
                space_id = str(space["id"])

                async for batch in self._get_folderless_lists(space_id, params):
                    yield batch

                folders_response = await self.client.send_api_request(
                    f"/v2/space/{space_id}/folder",
                    params={"archived": str(include_archived).lower()},
                )

                for folder in folders_response.get("folders", []):
                    folder_id = str(folder["id"])
                    async for batch in self._get_lists_from_folder(folder_id, params):
                        yield batch

    async def get_single_resource(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Get a single list by ID.

        Endpoint: GET /v2/list/{list_id}
        """
        response = await self.client.send_api_request(f"/v2/list/{resource_id}")
        return response if response else None
