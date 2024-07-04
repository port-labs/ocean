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

        self.page_size = 50

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

    # Teams
    async def _get_teams(self) -> dict[str, Any]:
        team_response = await self.client.get(f"{self.clickup_api_url}/team")
        team_response.raise_for_status()

        return team_response.json()

    async def get_teams(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        logger.info("Getting teams from Clickup")

        team_list = (await self._get_teams())["teams"]
        if not team_list:
            logger.warning(
                "Team query returned 0 teams, did you provide the correct ClickUp credentials?"
            )

        yield team_list

    # Spaces
    async def _get_spaces(self, team_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        team_response = await self.client.get(
            f"{self.clickup_api_url}/team/{team_id}/space", params=params
        )
        team_response.raise_for_status()

        return team_response.json()

    async def get_paginated_spaces(
        self, team_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting spaces from Clickup")

        params = self._generate_base_req_params()

        all_spaces = (await self._get_spaces(team_id, params))["spaces"]

        params["page_size"] = self.page_size
        page = 0

        while page * self.page_size < len(all_spaces):
            space_list = (await self._get_spaces(team_id, params))["spaces"]
            yield space_list
            page += 1

    # Folders
    async def _get_folders(
        self, space_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        folder_response = await self.client.get(
            f"{self.clickup_api_url}/space/{space_id}/folder", params=params
        )
        folder_response.raise_for_status()

        return folder_response.json()

    # Projects

    async def _get_projects(
        self, folder_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        team_response = await self.client.get(
            f"{self.clickup_api_url}/folder/{folder_id}/list"
        )
        team_response.raise_for_status()

        yield team_response.json()

    async def _get_projects_with_no_folders(
        self, space_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:

        response = await self.client.get(
            f"{self.clickup_api_url}/space/{space_id}/list", params=params
        )

        return response.json()

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

        projects_with_no_folder = (
            await self._get_projects_with_no_folders(space_id, params)
        )["lists"]
        all_projects = projects_with_no_folder + the_projects

        if not all_projects:
            logger.warning("Space query returned 0 projects")

        params["page_size"] = self.page_size
        page = 0
        while page * self.page_size < len(all_projects):
            all_folders_resp = (await self._get_folders(space_id, params))["folders"]
            projects_in_folders = [folder["lists"] for folder in all_folders_resp]
            the_projects = [
                project for sublist in projects_in_folders for project in sublist
            ]

            projects_with_no_folder = (
                await self._get_projects_with_no_folders(space_id, params)
            )["lists"]

            projects = projects_with_no_folder + the_projects
            yield projects
            page += 1

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

    # Issues This is same thing as tasks on clickup
    async def _get_issues(self, list_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        issue_response = await self.client.get(
            f"{self.clickup_api_url}/list/{list_id}/task", params=params
        )
        issue_response.raise_for_status()

        return issue_response.json()

    async def create_events_webhook(self, app_host: str) -> None:
        pass

    async def get_paginated_issues(
        self,
        list_id: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:

        params = self._generate_base_req_params()
        all_issues = (await self._get_issues(list_id, params))["tasks"]

        if not all_issues:
            logger.warning(
                "Issues query returned 0 issues, did you provide the correct ClickUp  credentials"
            )

        params["page_size"] = self.page_size
        page = 0

        while page * self.page_size < len(all_issues):

            all_issues = (await self._get_issues(list_id, params))["tasks"]
            yield all_issues
            page += 1

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
