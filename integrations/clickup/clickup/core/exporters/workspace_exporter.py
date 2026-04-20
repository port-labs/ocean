from typing import Any, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.clients.http.clickup_client import ClickUpClient
from clickup.core.exporters.abstract_exporter import AbstractClickUpExporter


class WorkspaceExporter(AbstractClickUpExporter[ClickUpClient]):
    """Exporter for ClickUp Workspaces (called 'Teams' in API v2).

    Endpoint: GET /v2/team
    Returns: List of authorized workspaces for the authenticated user

    Note: ClickUp API v2 uses 'team' terminology, but v3 uses 'workspace'.
    We use 'workspace' for clarity in Port's catalog.

    Reference: https://developer.clickup.com/reference/getauthorizedteams
    """

    async def get_paginated_resources(
        self, options: Optional[Any] = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all authorized workspaces.

        This endpoint returns all workspaces in a single response (no pagination).
        """
        logger.info("Fetching authorized workspaces from ClickUp")

        response = await self.client.send_api_request("/v2/team")

        if not response:
            logger.warning("No workspaces returned from ClickUp API")
            return

        teams = response.get("teams", [])
        if teams:
            logger.info(f"Fetched {len(teams)} workspaces from ClickUp")
            yield teams

    async def get_single_resource(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Get a single workspace by ID.

        Note: ClickUp doesn't have a direct 'get single workspace' endpoint.
        We fetch all workspaces and filter by ID.
        """
        response = await self.client.send_api_request("/v2/team")

        if not response:
            return None

        teams = response.get("teams", [])
        for team in teams:
            if str(team.get("id")) == str(resource_id):
                return team

        logger.warning(f"Workspace {resource_id} not found")
        return None
