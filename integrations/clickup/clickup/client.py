from typing import Any, AsyncGenerator
import httpx
from loguru import logger
from port_ocean.utils import http_async_client


class ClickUpClient:
    def __init__(self, clickup_url: str, clickup_api_key: str) -> None:
        self.api_url = f"{clickup_url}/api/v2"
        self.api_auth_header = {"Authorization": clickup_api_key}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.client.timeout = httpx.Timeout(30)  # 30 seconds timeout for requests

    @staticmethod
    def parse_projects_from_folders(folders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        folder_with_projects = [folder["lists"] for folder in folders]
        flattened_projects = [
            project for sublist in folder_with_projects for project in sublist
        ]
        return flattened_projects

    @staticmethod
    def _generate_base_req_params(page: int = 0) -> dict[str, Any]:
        return {"page": page}

    async def _get(self, endpoint: str, params: dict[str, Any] = None) -> dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()


    async def get_projects(self, space_id: str, team_id: str) -> list[dict[str, Any]]:
        logger.info("Getting projects from ClickUp")

        try:
            foldered_projects = self.parse_projects_from_folders(
                (await self._get(f"/space/{space_id}/folder"))["folders"]
            )
            folderless_projects = (await self._get(f"/space/{space_id}/list"))["lists"]
            projects = folderless_projects + foldered_projects

            if not projects:
                logger.warning("Space query returned 0 projects")

            return [{**project, "__team_id": team_id} for project in projects]
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch projects for space_id {space_id}: {e}")
            return []

    async def get_all_projects(self):
        teams = await self.get_teams()
        for team in teams:
            team_id = team["id"]
            spaces = await self.get_spaces(team_id)
            logger.info(f"Received spaces batch with {len(spaces)} spaces for team {team_id}")
            for space in spaces:
                space_id = space["id"]
                projects = await self.get_projects(space_id, team_id)
                return projects, team_id

    async def get_teams(self) -> list[dict[str, Any]]:
        logger.info("Getting teams from ClickUp")
        try:
            total_teams = (await self._get("/team"))["teams"]
            return total_teams
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch teams: {e}")
            return []

    async def get_spaces(self, team_id: str) -> list[dict[str, Any]]:
        logger.info("Getting spaces from ClickUp")

        try:
            space_response_list = (await self._get(f"/team/{team_id}/space"))["spaces"]
            return space_response_list
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch spaces for team_id: {team_id}: {e}")
            return []

    async def get_paginated_issues(
        self
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting tasks (issues) from ClickUp")
        projects, _ = await self.get_all_projects()
        for project in projects:
            project_id = project["id"]
            params = self._generate_base_req_params()
            page = params.get("page", 0)
            while True:
                logger.info(f"Current query position: page {page}")
                try:
                    task_response = await self._get(f"/list/{project_id}/task", params)
                    task_response_list = task_response.get("tasks", [])
                    yield task_response_list
                    if not task_response_list:
                        break
                except httpx.HTTPStatusError as e:
                    logger.error(f"Failed to fetch tasks for page {page}: {e}")
                    break
                page += 1
                params["page"] = page
