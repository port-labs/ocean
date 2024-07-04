from typing import Any, AsyncGenerator
from httpx import Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from enum import StrEnum
from port_ocean.context.event import event

class CacheKeys(StrEnum):
    TEAMS = "teams"
    TEAM = "team" 
    PROJECTS = "projects"

class ClickupClient:
    def __init__(self, clickup_url: str, clickup_apikey: str) -> None:
        self.clickup_url = clickup_url
        self.api_auth_header = {"Authorization": clickup_apikey}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.client.timeout = Timeout(30)
    
    @staticmethod
    def _generate_base_req_params(page: int = 0) -> dict[str, Any]:
        return {"page": page}
    
    async def get_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting teams from Clickup")
        url = f"{self.clickup_url}/team"
        team_response = await self.client.get(url)
        team_response.raise_for_status()
        team_list = team_response.json()["teams"]
        event.attributes[CacheKeys.TEAMS] = team_list
        yield team_list

    async def get_spaces(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting spaces from Clickup")
        team_list: list[dict[str, Any]] = event.attributes.get(CacheKeys.TEAMS, [])
        if not team_list:
            async for team_list in self.get_teams():
                async for spaces in self._fetch_spaces_for_teams(team_list):
                    yield spaces
        else:
            async for spaces in self._fetch_spaces_for_teams(team_list):
                yield spaces
    
    async def _fetch_spaces_for_teams(self, team_list: list[dict[str, Any]]) -> AsyncGenerator[list[dict[str, Any]], None]:
        for team_dict in team_list:
            url = f'{self.clickup_url}/team/{team_dict["id"]}/space'
            space_response = await self.client.get(url)
            space_response.raise_for_status()
            space_list = space_response.json()["spaces"]
            event.attributes[CacheKeys.TEAM] = team_dict
            yield space_list
    
    async def get_folders(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting folders from Clickup")
        async for space_list in self.get_spaces():
            for space_dict in space_list:
                url = f'{self.clickup_url}/space/{space_dict["id"]}/folder'
                folder_response = await self.client.get(url)
                folder_response.raise_for_status()
                folder_list = folder_response.json()["folders"]
                yield folder_list

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Clickup")
        async for folder_list in self.get_folders():
            async for projects in self._fetch_projects_for_folders(folder_list):
                yield projects
        async for space_list in self.get_spaces():
            async for projects in self._fetch_projects_for_spaces(space_list):
                yield projects
    
    async def _fetch_projects_for_folders(self, folder_list: list[dict[str, Any]]) -> AsyncGenerator[list[dict[str, Any]], None]:
        for folder_dict in folder_list:
            url = f'{self.clickup_url}/folder/{folder_dict["id"]}/list'
            project_response = await self.client.get(url)
            project_response.raise_for_status()
            project_list = project_response.json()["lists"]
            team: dict[str, Any] = event.attributes.get(CacheKeys.TEAM, {})
            project_list_with_team = [{**project, "__team": team} for project in project_list]
            self._cache_projects(project_list_with_team)
            yield project_list_with_team

    async def _fetch_projects_for_spaces(self, space_list: list[dict[str, Any]]) -> AsyncGenerator[list[dict[str, Any]], None]:
        for space_dict in space_list:
            url = f'{self.clickup_url}/space/{space_dict["id"]}/list'
            project_response = await self.client.get(url)
            project_response.raise_for_status()
            project_list = project_response.json()["lists"]
            team: dict[str, Any] = event.attributes.get(CacheKeys.TEAM, {})
            project_list_with_team = [{**project, "__team": team} for project in project_list]
            self._cache_projects(project_list_with_team)
            yield project_list_with_team

    def _cache_projects(self, project_list_with_team: list[dict[str, Any]]) -> None:
        project_list_with_team_cache: list[dict[str, Any]] = event.attributes.get(CacheKeys.PROJECTS, [])
        project_list_with_team_cache.extend(project_list_with_team)
        event.attributes[CacheKeys.PROJECTS] = project_list_with_team_cache

    async def get_paginated_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Clickup")
        project_list: list[dict[str, Any]] = event.attributes.get(CacheKeys.PROJECTS, [])
        if not project_list:
            async for project_list in self.get_projects():
                async for issues in self._fetch_issues_for_projects(project_list):
                    yield issues
        else:
            async for issues in self._fetch_issues_for_projects(project_list):
                yield issues

    async def _fetch_issues_for_projects(self, project_list: list[dict[str, Any]]) -> AsyncGenerator[list[dict[str, Any]], None]:
        for project_dict in project_list:
            url = f'{self.clickup_url}/list/{project_dict["id"]}/task'
            params = self._generate_base_req_params()
            last_page = False
            while not last_page:
                task_response = await self.client.get(url, params=params)
                task_response.raise_for_status()
                task_list = task_response.json()["tasks"]
                if not task_list:
                    last_page = True
                yield task_list
                params["page"] += 1

