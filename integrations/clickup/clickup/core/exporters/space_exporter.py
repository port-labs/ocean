from typing import Any, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.clients.http.clickup_client import ClickUpClient
from clickup.core.exporters.abstract_exporter import AbstractClickUpExporter


class SpaceExporter(AbstractClickUpExporter[ClickUpClient]):
    """Exporter for ClickUp Spaces.

    Endpoint: GET /v2/team/{team_id}/space
    Returns: List of spaces in a workspace

    Reference: https://developer.clickup.com/reference/getspaces
    """

    async def get_paginated_resources(
        self,
        options: Optional[dict[str, Any]] = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all spaces across all workspaces.

        Args:
            options: Optional dict with:
                - workspace_id: Fetch spaces for specific workspace only
                - archived: Include archived spaces (default: False)
        """
        options = options or {}
        workspace_id = options.get("workspace_id")
        include_archived = options.get("archived", False)

        if workspace_id:
            workspace_ids = [workspace_id]
        else:
            workspaces_response = await self.client.send_api_request("/v2/team")
            workspace_ids = [
                str(team["id"]) for team in workspaces_response.get("teams", [])
            ]

        for ws_id in workspace_ids:
            logger.info(f"Fetching spaces for workspace {ws_id}")

            params = {"archived": str(include_archived).lower()}
            response = await self.client.send_api_request(
                f"/v2/team/{ws_id}/space",
                params=params,
            )

            if not response:
                continue

            spaces = response.get("spaces", [])
            if spaces:
                for space in spaces:
                    space["__workspace_id"] = ws_id

                logger.info(f"Fetched {len(spaces)} spaces from workspace {ws_id}")
                yield spaces

    async def get_single_resource(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Get a single space by ID.

        Endpoint: GET /v2/space/{space_id}
        """
        response = await self.client.send_api_request(f"/v2/space/{resource_id}")
        return response if response else None
