from typing import Any, AsyncGenerator, Optional, List
from httpx import Timeout
from loguru import logger
from .utils import CustomProperties
from port_ocean.utils import http_async_client

PAGE_SIZE = 50

WEBHOOK_EVENTS = [
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
    "folderCreated",
    "folderUpdated",
    "folderDeleted",
]


class ClickupClient:
    def __init__(self, clickup_url: str, clickup_token: str):
        self.clickup_url = clickup_url
        self.clickup_token = clickup_token
        self.api_url = f"{self.clickup_url}/api/v2"
        self.client = http_async_client
        self.client.timeout = Timeout(30)
        self.team_key = None

    async def initialize_team_key(self):
        self.team_key = await self.get_team_key()

    @property
    async def api_headers(self) -> dict[str, Any]:
        return {
            "Authorization": self.clickup_token,
            "Content-Type": "application/json",
        }

    async def get_team_key(self) -> List[str]:
        url = f"{self.api_url}/team"
        response = await self._send_api_request(url)
        teams = response.get("teams", [])
        team_ids = []
        for team in teams:
            team_ids.append(team.get("id"))
        return team_ids

    async def _send_api_request(self, url: str, params: Optional[dict[str, Any]] = None,
                                json_data: Optional[dict[str, Any]] = None, method: str = "GET") -> Any:
        logger.debug(f"Sending request {method} to endpoint {url}")
        response = await self.client.request(url=url, method=method, headers=await self.api_headers, params=params,
                                             json=json_data)
        response.raise_for_status()
        return response.json()

    async def get_single_clickup_team(self, team_id: str) -> dict[str, Any]:
        url = f"{self.api_url}/team/{team_id}"
        response = await self._send_api_request(url)
        team = response.get('team')
        return team

    async def get_clickup_teams(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        url = f"{self.api_url}/team"
        response = await self._send_api_request(url)
        teams = response.get("teams", [])
        yield teams

    async def _get_spaces_in_team(self, team_id: str) -> AsyncGenerator[str, None]:
        url = f"{self.api_url}/team/{team_id}/space"
        params = {"archived": "false"}
        response = await self._send_api_request(url, params)
        spaces = response.get("spaces")
        for space in spaces:
            yield space.get("id")

    async def _get_folders_in_space(self, team_id: str) -> AsyncGenerator[str, None]:
        async for space in self._get_spaces_in_team(team_id):
            url = f"{self.api_url}/space/{space}/folder"
            params = {"archived": "false"}
            response = await self._send_api_request(url, params)
            folders = response.get("folders")
            for folder in folders:
                yield folder.get("id")

    async def get_folder_projects(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        for team_id in self.team_key:
            async for folder_id in self._get_folders_in_space(team_id):
                url = f"{self.api_url}/folder/{folder_id}/list"
                params = {"archived": "false"}
                response = await self._send_api_request(url, params)
                projects = response.get("lists")
                yield [
                    {**project, CustomProperties.TEAM_ID: team_id}
                    for project in projects
                ]

    async def get_folderless_projects(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        for team_id in self.team_key:
            async for space_id in self._get_spaces_in_team(team_id):
                url = f"{self.api_url}/space/{space_id}/list"
                params = {"archived": "false"}
                response = await self._send_api_request(url, params)
                projects = response.get("lists")
                yield [
                    {**project, CustomProperties.TEAM_ID: team_id}
                    for project in projects
                ]

    async def get_single_project(self, folder_id: str) -> dict[str, Any]:
        url = f"{self.api_url}/folder/{folder_id}"
        response = await self._send_api_request(url)
        return response

    async def get_paginated_issues(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        if self.team_key is None:
            await self.initialize_team_key()
        for team_id in self.team_key:
            url = f"{self.api_url}/team/{team_id}/task"
            page = 0
            while True:
                params = {"page": page}
                response = await self._send_api_request(url, params)
                yield response.get("tasks")
                if response.get("last_page"):
                    break
                page += 1

    async def get_single_issue(self, task_id: str) -> dict[str, Any]:
        url = f"{self.api_url}/task/{task_id}"
        issue_response = await self._send_api_request(url)
        return issue_response

    async def create_events_webhook(self, app_host: str) -> None:
        if self.team_key is None:
            await self.initialize_team_key()
        for team_id in self.team_key:
            webhook_target_app_host = f"{app_host}/integration/webhook"
            clickup_get_webhook_url = f"{self.api_url}/team/{team_id}/webhook"
            webhook_check_response = await self._send_api_request(clickup_get_webhook_url)
            webhook_check = webhook_check_response.get("webhooks")

            for webhook in webhook_check:
                if webhook["endpoint"] == webhook_target_app_host:
                    logger.info("Ocean real-time reporting webhook already exists on ClickUp")
                    return

            body = {
                "endpoint": webhook_target_app_host,
                "events": WEBHOOK_EVENTS,
            }
            logger.info("Subscribing to ClickUp webhooks...")
            webhook_create_response = await self._send_api_request(clickup_get_webhook_url, json_data=body,
                                                                   method="POST")
            logger.info(f"Ocean real-time reporting webhook created on ClickUp - {webhook_create_response}")
