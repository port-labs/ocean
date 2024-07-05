from port_ocean.utils import http_async_client
from httpx import Timeout
from typing import AsyncGenerator, Any


class ClickUpClient:

    def __init__(self, click_up_token: str) -> None:

        self.click_up_api_url = "https://api.clickup.com/api/v2"
        self.click_up_token = click_up_token
        self.client = http_async_client
        self.client.headers = {
            "Authorization": self.click_up_token,
            **self.client.headers,
        }
        self.client.timeout = Timeout(30)

    async def __generate_teams(self):

        response = await self.client.get(url=f"{self.click_up_api_url}/team")

        response.raise_for_status()

        return response.json()

    async def __get_spaces(self, team_id: int):

        response = await self.client.get(url=f"{self.click_up_api_url}/{team_id}/space")

        response.raise_for_status()

        return response.json()

    async def __get_folder(self, space_id: str):

        response = await self.client.get(
            url=f"{self.click_up_api_url}/space/{space_id}/folder"
        )

        response.raise_for_status()

        return response.json()

    async def __get_projects(self, folder_id: int):
        response = await self.client.get(
            url=f"{self.click_up_api_url}/folder/{folder_id}/list"
        )

        response.raise_for_status()

        return response.json()

    async def __get_issues(self, list_id: int, page_count: int = 0):

        response = await self.client.get(
            url=f"{self.click_up_api_url}/list/{list_id}/task",
            params={"page": page_count},
        )

        response.raise_for_status()

        return response.json()

    async def get_single_issue(self, issue_id: str):

        response = await self.client.get(url=f"{self.click_up_api_url}/task/{issue_id}")

        response.raise_for_status()

        return response.json()

    async def get_single_project(self, project_id: int):
        response = await self.client.get(
            url=f"{self.click_up_api_url}/list/{project_id}"
        )

        response.raise_for_status()

        return response.json()

    async def get_teams(self) -> list[dict[str, Any]]:

        return await self.__generate_teams()["teams"]

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for team in await self.get_teams():
            spaces = await self.__get_spaces(team_id=team["id"])["spaces"]

            for space in spaces:
                folders = await self.__get_folder(space_id=space["id"])["folders"]

                yield folders["lists"]

    async def get_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for project in self.get_projects():

            page_count = 0
            paginated_data = True
            while paginated_data:

                tasks = await self.__get_issues(
                    list_id=project["id"], page_count=page_count
                )["tasks"]

                yield tasks

                if tasks["last_page"] is False:
                    paginated_data = False

                page_count += 1
