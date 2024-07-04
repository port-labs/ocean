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
    def __init__(self, clickup_url: str, clickup_apikey: str)-> None:
        self.clickup_url = clickup_url
        self.api_auth_header = {"Authorization": clickup_apikey}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.client.timeout = Timeout(30)
    
    @staticmethod
    def _generate_base_req_params(
        page: int = 0
    ) -> dict[str, Any]:
        return {
            "page": page,
        }
    
    
    async def get_teams(self)-> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting teams from Clickup")

        url = f"{self.clickup_url}/team"
        team_response = await self.client.get(url)
        team_response.raise_for_status()
        team_list = team_response.json()["teams"]

        # cache so that when we need to get other things that require team id we don't need to call API
        event.attributes[CacheKeys.TEAMS]=team_list  

        yield team_list
    

    async def get_spaces(self)-> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting spaces from Clickup using team_ids from cache")

        team_list = event.attributes.get(CacheKeys.TEAMS)
        for team_dict in team_list:
            url = f'{self.clickup_url}/team/{team_dict["id"]}/space'
            space_response = await self.client.get(url)
            space_response.raise_for_status()
            space_list = space_response.json()["spaces"]

            # record the present team to be useful for relation in get_projects() function
            event.attributes[CacheKeys.TEAM]=team_dict

            yield space_list


    async def get_folders(self)->AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting folders from Clickup using space_ids from get_spaces")

        async for space_list in self.get_spaces():
            for space_dict in space_list:
                url = f'{self.clickup_url}/space/{space_dict["id"]}/folder'
                folder_response = await self.client.get(url)
                folder_response.raise_for_status()
                folder_list = folder_response.json()["folders"]
                yield folder_list


    async def get_projects(self)->AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Clickup")

        async for folder_list in self.get_folders():
            for folder_dict in folder_list:
                url = f'{self.clickup_url}/folder/{folder_dict["id"]}/list'
                project_response = await self.client.get(url)
                project_response.raise_for_status()
                project_list = project_response.json()["lists"]
                team: dict = event.attributes.get(CacheKeys.TEAM)
                project_list_with_team = [{**project, "__team": team} for project in project_list]

                # cache so that when we need to get other things that require project id we don't need to call API
                project_list_with_team_cache: list =  event.attributes.get(CacheKeys.PROJECTS, [])
                project_list_with_team_cache.extend(project_list_with_team)
                event.attributes[CacheKeys.PROJECTS]=project_list_with_team_cache 

                yield project_list_with_team
            
            async for space_list in self.get_spaces():
                for space_dict in space_list:
                    url = f'{self.clickup_url}/space/{space_dict["id"]}/list'
                    project_response = await self.client.get(url)
                    project_response.raise_for_status()
                    project_list = project_response.json()["lists"]
                    team: dict = event.attributes.get(CacheKeys.TEAM)
                    project_list_with_team = [{**project, "__team": team} for project in project_list]

                    # cache so that when we need to get other things that require project id we don't need to call API
                    project_list_with_team_cache: list =  event.attributes.get(CacheKeys.PROJECTS, [])
                    project_list_with_team_cache.extend(project_list_with_team)
                    event.attributes[CacheKeys.PROJECTS]=project_list_with_team_cache

                    yield project_list_with_team


    async def get_paginated_issues(self)->AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Clickup")

        project_list = event.attributes.get(CacheKeys.PROJECTS)
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

