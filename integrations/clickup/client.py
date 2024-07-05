from typing import Any, AsyncGenerator, Dict, List

from httpx import Timeout

from loguru import logger


from port_ocean.utils import http_async_client


class ClickUpClient:
    def __init__(self, clickup_token: str) -> None:
        self.clickup_url = "https://api.clickup.com"
        self.clickup_token = clickup_token
        self.clickup_api_url = f"{self.clickup_url}/api/v2"

        self.headers = {"Authorization": self.clickup_token}

        self.client = http_async_client

        self.page_size = 100

        self.client.headers.update(self.headers)
        self.client.timeout = Timeout(30)

    @staticmethod
    def _generate_base_req_params(page: int = 0) -> Dict[str, Any]:
        return {
            "page": page,
        }

    @staticmethod
    def update_project_team_id(project: Dict[str, Any], team_id: str) -> Dict[str, Any]:
        project["__team_id"] = team_id
        return project

    async def _get_teams(self) -> dict[str, Any]:
        try:
            team_response = await self.client.get(f"{self.clickup_api_url}/team")
            team_response.raise_for_status()
            return team_response.json()
        except httpx.HTTPError as e:
            logger.error(f"Encountered an HTTP error {e} trying to fetch team")
            raise

    async def get_teams(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        logger.info("Getting teams from Clickup")

        team_list = (await self._get_teams())["teams"]

        yield team_list

    async def _get_spaces(self, team_id: str) -> Dict[str, Any]:
        try:
            team_response = await self.client.get(
                f"{self.clickup_api_url}/team/{team_id}/space",
            )
            team_response.raise_for_status()

            return team_response.json()
        except httpx.HTTPError as e:
            logger.error(f"Encountered an HTTP error {e} trying to fetch spaces")
            raise

    async def get_paginated_spaces(
        self, team_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting spaces from Clickup")
        all_spaces = (await self._get_spaces(team_id))["spaces"]
        yield all_spaces

    async def _get_folders(
        self, space_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:

        try:
            folder_response = await self.client.get(
                f"{self.clickup_api_url}/space/{space_id}/folder", params=params
            )
            folder_response.raise_for_status()
            return folder_response.json()
        except httpx.HTTPError as e:
            logger.error(f"Encountered an HTTP error {e} trying to fetch folders")
            raise

    async def _get_projects(
        self, folder_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        team_response = await self.client.get(
            f"{self.clickup_api_url}/folder/{folder_id}/list"
        )
        team_response.raise_for_status()

        yield team_response.json()

    async def _get_projects_with_no_folders(self, space_id: str) -> Dict[str, Any]:
        try:

            response = await self.client.get(
                f"{self.clickup_api_url}/space/{space_id}/list",
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} trying to fetch projects with no folder"
            )
            raise

    async def get_paginated_projects(
        self, space_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:

        logger.info("Getting projects from ClickUp")

        params = self._generate_base_req_params()
        all_folders_resp = (await self._get_folders(space_id, params))["folders"]
        projects_in_folders = [folder["lists"] for folder in all_folders_resp]
        the_projects = [
            project for sublist in projects_in_folders for project in sublist
        ]
        yield the_projects

        projects_with_no_folder = (
            await self._get_projects_with_no_folders(space_id, params)
        )["lists"]

        yield projects_with_no_folder
        all_projects = projects_with_no_folder + the_projects

        yield all_projects

    async def get_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:

        async for teams in self.get_teams():
            for team in teams:
                team_id = team["id"]
                async for spaces in self.get_paginated_spaces(team_id):
                    for space in spaces:
                        space_id = space["id"]
                        async for projects in self.get_paginated_projects(space_id):

                            project_list = list(
                                map(
                                    lambda project: self.update_project_team_id(
                                        project, team_id
                                    ),
                                    projects,
                                )
                            )
                            yield project_list

    async def _get_issues(self, list_id: str) -> Dict[str, Any]:
        try:
            issue_response = await self.client.get(
                f"{self.clickup_api_url}/list/{list_id}/task",
            )
            issue_response.raise_for_status()

            return issue_response.json()
        except httpx.HTTPError as e:
            logger.error(f"Encountered an HTTP error {e} trying to fetch issues")
            raise

    async def get_paginated_issues(
        self,
        list_id: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:

        all_issues = (await self._get_issues(list_id))["tasks"]

        yield all_issues

    async def get_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:

        async for teams in self.get_teams():
            for team in teams:
                team_id = team["id"]
                async for spaces in self.get_paginated_spaces(team_id):
                    for space in spaces:
                        space_id = space["id"]
                        async for projects in self.get_paginated_projects(space_id):
                            for project in projects:
                                project_id = project["id"]
                                async for issues in self.get_paginated_issues(
                                    project_id
                                ):
                                    yield issues
