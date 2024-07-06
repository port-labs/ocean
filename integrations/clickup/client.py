from enum import StrEnum
import typing
from typing import Any, AsyncGenerator
import httpx

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

    async def get_teams(self) -> list[dict[str, Any]]:
        try:
            team_response = await self.client.get(f"{self.clickup_api_url}/team")
            team_response.raise_for_status()
            return team_response.json().get("teams")
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {team_response}"
            )
            raise

    async def _get_spaces(self) -> list[dict[str, Any]]:
        try:
            for team_ in self.get_teams():
                team_id = team_["id"]
                folder_response = await self.client.get(
                    f"{self.clickup_api_url}/folder/{team_id}/space"
                )
                folder_response.raise_for_status()
                return folder_response.json().get("spaces")

        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {folder_response}"
            )
            raise

    async def _get_folders(self) -> list[dict[str, Any]]:
        try:
            for space_ in self._get_spaces():
                space_id = space_["id"]
                folder_response = await self.client.get(
                    f"{self.clickup_api_url}/space/{space_id}/folder"
                )
                folder_response.raise_for_status()
                return folder_response.json().get("folders")

        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {folder_response}"
            )
            raise

    async def get_lists(self) -> list[dict[str, Any]]:
        try:
            for folder_ in self._get_folders():
                folder_id = folder_["id"]
                list_response = await self.client.get(
                    f"{self.clickup_api_url}/folder/{folder_id}/list"
                )
                list_response.raise_for_status()
                return list_response.json()

        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {list_response}"
            )
            raise

    async def get_issues(self) -> list[dict[str, Any]]:
        try:
            for list_ in self.get_lists.get("lists"):
                list_id = list_["id"]
                issue_response = await self.client.get(
                    f"{self.clickup_api_url}/list/{list_id}/task"
                )
                issue_response.raise_for_status()
                return issue_response.json()

        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {issue_response}"
            )
            raise
