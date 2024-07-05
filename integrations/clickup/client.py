from typing import Any, AsyncGenerator

from httpx import Timeout
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result


class ClickupClient:
    def __init__(self, clickup_apikey: str) -> None:
        self.clickup_url = "https://api.clickup.com/api/v2"
        self.client = http_async_client
        self.client.headers.update({"Authorization": clickup_apikey})
        self.client.timeout = Timeout(30)

    @cache_iterator_result()
    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.clickup_url}/team"
        team_response = await self.client.get(url)
        team_response.raise_for_status()
        team_list = team_response.json()["teams"]
        yield team_list

    @cache_iterator_result()
    async def get_spaces(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self.get_teams():
            for team in teams:
                yield await self._get_spaces(team["id"])

    async def _get_spaces(self, team_id: str) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/team/{team_id}/space"
        response = await self.client.get(url)
        response.raise_for_status()
        spaces = response.json()["spaces"]
        return [{**space, "__team_id": team_id} for space in spaces]

    @cache_iterator_result()
    async def get_folders(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for spaces in self.get_spaces():
            for space in spaces:
                yield await self._get_folders(space["id"], space["__team_id"])

    async def _get_folders(self, space_id: str, team_id: str) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/space/{space_id}/folder"
        response = await self.client.get(url)
        response.raise_for_status()
        folders = response.json()["folders"]
        return [{**folder, "__team_id": team_id} for folder in folders]

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for folders in self.get_folders():
            for folder in folders:
                yield await self._get_projects(folder["id"], folder["__team_id"])

    async def _get_projects(self, folder_id: str, team_id: str) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/folder/{folder_id}/list"
        response = await self.client.get(url)
        response.raise_for_status()
        projects = response.json()["lists"]
        return [{**project, "__team_id": team_id} for project in projects]

    async def get_paginated_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_projects():
            for project in projects:
                async for issues in self._get_issues(project["id"]):
                    yield issues

    async def _get_issues(
        self, project_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.clickup_url}/list/{project_id}/task"
        params = {"page": 0}
        last_page = False
        while not last_page:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            tasks = response.json()["tasks"]
            yield tasks
            last_page = not tasks
            params["page"] += 1
