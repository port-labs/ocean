from enum import StrEnum
import typing
from typing import Any, AsyncGenerator

from httpx import Timeout
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"

class ClickupClient:
    def __init__(self, clickup_api_token: str) -> None:
        self.clickup_api_url = "https://api.clickup.com/api/v2"
        self.clickup_api_token = clickup_api_token

        self.api_auth_header = {"Authorization": self.clickup_api_token}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)

        self.client.timeout = Timeout(30)

    # gets the list of teams, kind=team
    async def get_teams(self) -> list[dict[str, Any]]:
        team_response = await self.client.get(f"{self.clickup_api_url}/team")
        team_response.raise_for_status()
        return team_response.json()
    
    # gets the spaces, to be used for getting folders
    async def get_spaces(self) -> list[dict[str, Any]]:
        team_id = get_teams().get("teams")[0]["id"]
        folder_response = await self.client.get(f"{self.clickup_api_url}/folder/{team_id}/space")
        folder_response.raise_for_status()
        return folder_response.json().get("spaces")
    
    # gets the folders, to be used for getting list of kind=project
    async def get_folders(self) -> list[dict[str, Any]]:
        for space_ in self.get_spaces():
            space_id = space_["id"]
            folder_response = await self.client.get(f"{self.clickup_api_url}/space/{space_id}/folder")
            folder_response.raise_for_status()
            return folder_response.json().get("folders")
    
    # gets the list of project, kind=project
    async def get_lists(self) -> list[dict[str, Any]]:
        for folder_ in self.get_folders():
            folder_id = folder_["id"]
            list_response = await self.client.get(f"{self.clickup_api_url}/folder/{folder_id}/list")
            list_response.raise_for_status()
            return list_response.json()

    # gets the list of tasks, kind=issue
    async def get_issues(self) -> list[dict[str, Any]]:
        for list_ in self.get_lists.get("lists"):
            list_id = list_["id"]
            issue_response = await self.client.get(f"{self.clickup_api_url}/list/{list_id}/task")
            issue_response.raise_for_status()
            return issue_response.json()