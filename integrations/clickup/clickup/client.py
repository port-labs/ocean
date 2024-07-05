from typing import Any, AsyncGenerator, Optional, List
from httpx import Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

WEBHOOK_EVENTS = [
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
    "listCreated",
    "listUpdated",
    "listDeleted",
]


class ClickupClient:
    """Clickup client to interact with Clickup API."""

    def __init__(self, clickup_url: str, clickup_token: str):
        self.clickup_url = clickup_url
        self.clickup_token = clickup_token
        self.api_url = f"{self.clickup_url}/api/v2"
        self.client = http_async_client
        self.client.timeout = Timeout(30)

    @property
    def api_headers(self) -> dict[str, Any]:
        return {
            "Authorization": self.clickup_token,
            "Content-Type": "application/json",
        }

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send a request to the Clickup API."""
        logger.debug(f"Sending request {method} to endpoint {url}")
        response = await self.client.request(
            url=url,
            method=method,
            headers=self.api_headers,
            params=params,
            json=json_data,
        )
        response.raise_for_status()
        return response.json()

    @cache_iterator_result()
    async def get_clickup_teams(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all Clickup teams."""
        url = f"{self.api_url}/team"
        yield (await self._send_api_request(url)).get("teams", [])

    @cache_iterator_result()
    async def _get_spaces_in_team(
        self, team_id: str
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all spaces in a workspace."""
        url = f"{self.api_url}/team/{team_id}/space"
        params = {"archived": "false"}
        yield (await self._send_api_request(url, params)).get("spaces", [])

    async def _get_folders_in_space(
        self, team_id: str
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all folders in a space."""
        async for spaces in self._get_spaces_in_team(team_id):
            for space in spaces:
                url = f"{self.api_url}/space/{space.get('id')}/folder"
                params = {"archived": "false"}
                yield (await self._send_api_request(url, params)).get("folders")

    async def get_folder_projects(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all projects with a folder parent."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                team_id = team.get("id")
                async for folders in self._get_folders_in_space(team_id):
                    for folder in folders:
                        url = f"{self.api_url}/folder/{folder.get('id')}/list"
                        params = {"archived": "false"}
                        response = await self._send_api_request(url, params)
                        projects = response.get("lists")
                        yield [
                            {**project, "__team_id": team_id} for project in projects
                        ]

    async def get_folderless_projects(
        self,
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all projects without a folder parent."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                team_id = team.get("id")
                async for spaces in self._get_spaces_in_team(team_id):
                    for space in spaces:
                        url = f"{self.api_url}/space/{space.get('id')}/list"
                        params = {"archived": "false"}
                        response = await self._send_api_request(url, params)
                        projects = response.get("lists")
                        yield [
                            {**project, "__team_id": team_id} for project in projects
                        ]

    async def get_single_project(self, list_id: str) -> dict[str, Any]:
        """Get a single project by folder_id."""
        url = f"{self.api_url}/list/{list_id}"
        response = await self._send_api_request(url)
        return response

    async def get_paginated_issues(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all issues in a project."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                url = f"{self.api_url}/team/{team.get('id')}/task"
                page = 0
                while True:
                    params = {"page": page}
                    response = await self._send_api_request(url, params)
                    yield response.get("tasks")
                    if response.get("last_page"):
                        break
                    page += 1

    async def get_single_issue(self, task_id: str) -> dict[str, Any]:
        """Get a single issue by task_id."""
        url = f"{self.api_url}/task/{task_id}"
        issue_response = await self._send_api_request(url)
        return issue_response

    async def create_events_webhook(self, app_host: str) -> None:
        """Create a webhook for ClickUp events."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                team_id = team.get("id")
                webhook_target_app_host = f"{app_host}/integration/webhook"
                clickup_get_webhook_url = f"{self.api_url}/team/{team_id}/webhook"
                webhook_check_response = await self._send_api_request(
                    clickup_get_webhook_url
                )
                webhook_check = webhook_check_response.get("webhooks")
                for webhook in webhook_check:
                    if webhook["endpoint"] == webhook_target_app_host:
                        logger.info(
                            "Ocean real-time reporting webhook already exists on ClickUp"
                        )
                        return

                body = {
                    "endpoint": webhook_target_app_host,
                    "events": WEBHOOK_EVENTS,
                }
                logger.info("Subscribing to ClickUp webhooks...")
                webhook_create_response = await self._send_api_request(
                    clickup_get_webhook_url, json_data=body, method="POST"
                )
                logger.info(
                    f"Ocean real-time reporting webhook created on ClickUp - {webhook_create_response}"
                )
