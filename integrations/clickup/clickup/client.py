from typing import Any, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client



class ClickUpClient:
    def __init__(self, clickup_url: str, clickup_api_key: str) -> None:
        self.clickup_url = clickup_url
        self.api_url = f"{self.clickup_url}/api/v2"

        self.api_auth_header = {"Authorization": clickup_api_key}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.client.timeout = httpx.Timeout(30)  # 30 seconds timeout for requests

    @staticmethod
    def parse_projects_from_folders(folders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        folder_with_projects = [folder["lists"] for folder in folders]
        flattened_projects = [project for sublist in folder_with_projects for project in sublist]
        return flattened_projects

    @staticmethod
    def _generate_base_req_params(page: int = 0) -> dict[str, Any]:
        return {"page": page}

    async def _get(self, endpoint: str, params: dict[str, Any] = None) -> dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _get_teams(self) -> dict[str, Any]:
        return await self._get("/team")

    async def _get_spaces(self, team_id: str) -> dict[str, Any]:
        return await self._get(f"/team/{team_id}/space")

    async def _get_tasks(self, list_id: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self._get(f"/list/{list_id}/task", params)

    async def _get_folderless_projects(self, space_id: str) -> dict[str, Any]:
        return await self._get(f"/space/{space_id}/list")

    async def _get_folders(self, space_id: str) -> dict[str, Any]:
        return await self._get(f"/space/{space_id}/folder")

    async def get_projects(
        self, space_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from ClickUp")

        foldered_projects = self.parse_projects_from_folders(
            (await self._get_folders(space_id))["folders"]
        )
        folderless_projects = (await self._get_folderless_projects(space_id))["lists"]
        projects = folderless_projects + foldered_projects

        if not projects:
            logger.warning("Space query returned 0 projects")

        yield projects

    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting teams from ClickUp")
        total_teams = (await self._get_teams())["teams"]

        if not total_teams:
            logger.warning(
                "Team query returned 0 teams, did you provide the correct ClickUp API credentials?"
            )

        yield total_teams

    async def get_spaces(
        self, team_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting spaces from ClickUp")

        total_spaces = (await self._get_spaces(team_id))["spaces"]

        if not total_spaces:
            logger.warning(
                "Space query returned 0 spaces, did you provide the correct ClickUp API credentials?"
            )

        space_response_list = (await self._get_spaces(team_id))["spaces"]
        yield space_response_list

    async def get_paginated_tasks(
        self, list_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting tasks (issues) from ClickUp")

        params = self._generate_base_req_params()

        page = params.get("page",0)
        while True:
            logger.info(f"Current query position: page {page}")
            try:
                task_response = await self._get_tasks(list_id, params)
                task_response_list = task_response.get("tasks", [])
                yield task_response_list
                if not task_response_list:
                    break
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to fetch tasks for page {page}: {e}")
                break
            page += 1
            params["page"] = page
