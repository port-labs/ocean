from typing import Any, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.clients.http.clickup_client import ClickUpClient
from clickup.core.exporters.abstract_exporter import AbstractClickUpExporter


class FolderExporter(AbstractClickUpExporter[ClickUpClient]):
    """Exporter for ClickUp Folders.

    Endpoint: GET /v2/space/{space_id}/folder
    Returns: List of folders in a space

    Reference: https://developer.clickup.com/reference/getfolders
    """

    async def get_paginated_resources(
        self,
        options: Optional[dict[str, Any]] = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all folders across all spaces.

        Args:
            options: Optional dict with:
                - space_id: Fetch folders for specific space only
                - archived: Include archived folders (default: False)
        """
        options = options or {}
        space_id = options.get("space_id")
        include_archived = options.get("archived", False)

        if space_id:
            space_ids = [space_id]
        else:
            workspaces_response = await self.client.send_api_request("/v2/team")
            space_ids = []

            for team in workspaces_response.get("teams", []):
                ws_id = str(team["id"])
                spaces_response = await self.client.send_api_request(
                    f"/v2/team/{ws_id}/space",
                    params={"archived": "false"},
                )
                for space in spaces_response.get("spaces", []):
                    space_ids.append(str(space["id"]))

        for sp_id in space_ids:
            logger.info(f"Fetching folders for space {sp_id}")

            params = {"archived": str(include_archived).lower()}
            response = await self.client.send_api_request(
                f"/v2/space/{sp_id}/folder",
                params=params,
            )

            if not response:
                continue

            folders = response.get("folders", [])
            if folders:
                for folder in folders:
                    folder["__space_id"] = sp_id

                logger.info(f"Fetched {len(folders)} folders from space {sp_id}")
                yield folders

    async def get_single_resource(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Get a single folder by ID.

        Endpoint: GET /v2/folder/{folder_id}
        """
        response = await self.client.send_api_request(f"/v2/folder/{resource_id}")
        return response if response else None
