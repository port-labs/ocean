from typing import Any, AsyncGenerator, Optional, List
from httpx import Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

TEAM_OBJ = "__team"
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

    def __init__(self, clickup_url: str, clickup_token: str, archived: bool):
        self.clickup_url = clickup_url
        self.clickup_token = clickup_token
        self.api_url = f"{self.clickup_url}/api/v2"
        self.client = http_async_client
        self.client.timeout = Timeout(30)
        self.archived = archived

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
        yield (await self._send_api_request(url, {"archived": self.archived})).get(
            "spaces", []
        )

    @cache_iterator_result()
    async def _get_folders_in_space(
        self, team_id: str
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all folders in a space."""
        async for spaces in self._get_spaces_in_team(team_id):
            for space in spaces:
                url = f"{self.api_url}/space/{space.get('id')}/folder"
                yield (
                    await self._send_api_request(url, {"archived": self.archived})
                ).get("folders")

    async def get_folder_projects(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all projects with a folder parent."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                async for folders in self._get_folders_in_space(team.get("id")):
                    for folder in folders:
                        projects = folder.get("lists")
                        yield [{**project, TEAM_OBJ: team} for project in projects]

    async def get_folderless_projects(
        self,
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all projects without a folder parent."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                async for spaces in self._get_spaces_in_team(team.get("id")):
                    for space in spaces:
                        url = f"{self.api_url}/space/{space.get('id')}/list"
                        response = await self._send_api_request(
                            url, {"archived": self.archived}
                        )
                        projects = response.get("lists")
                        yield [{**project, TEAM_OBJ: team} for project in projects]

    async def get_single_project(self, list_id: str) -> Optional[dict[str, Any]]:
        """Get a single project by list_id."""
        url = f"{self.api_url}/list/{list_id}"
        response = await self._send_api_request(url)
        space_id = response.get("space").get("id")
        async for teams in self.get_clickup_teams():
            for team in teams:
                async for spaces in self._get_spaces_in_team(team.get("id")):
                    for space in spaces:
                        if space.get("id") == space_id:
                            response[TEAM_OBJ] = team
                            return response

    async def get_paginated_issues(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all issues in a project."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                url = f"{self.api_url}/team/{team.get('id')}/task"
                page = 0
                while True:
                    response = await self._send_api_request(url, {"page": page})
                    yield response.get("tasks")
                    if response.get("last_page"):
                        break
                    page += 1

    async def get_single_issue(self, task_id: str) -> dict[str, Any]:
        """Get a single issue by task_id."""
        url = f"{self.api_url}/task/{task_id}"
        issue_response = await self._send_api_request(url)
        return issue_response

    async def create_clickup_webhook(self, team_id: str, app_host: str) -> None:
        """
        Create a new webhook for a given team.
        """
        await self._send_api_request(
            f"{self.api_url}/team/{team_id}/webhook",
            method="POST",
            json_data={
                "endpoint": f"{app_host}/integration/webhook",
                "events": WEBHOOK_EVENTS,
            },
        )
        logger.info("Webhook created successfully")

    async def get_clickup_webhooks(self, team_id: str) -> list[dict[str, Any]]:
        """
        Retrieve existing webhooks for a given team.
        """
        return (await self._send_api_request(f"{self.api_url}/team/{team_id}/webhook"))["webhooks"]

    async def create_clickup_events_webhook(self, app_host: str) -> None:

        async for teams in self.get_clickup_teams():
            for team in teams:
                team_id = team["id"]

                webhook_target_url = f"{app_host}/integration/webhook"

                webhooks = await self.get_clickup_webhooks(team_id)

                webhook_exits = any(
                    config["endpoint"] == webhook_target_url for config in webhooks
                )

                if webhook_exits:
                    logger.info(f"Webhook already exists for team {team_id}")
                else:
                    logger.info(f"Creating webhook for team {team_id}")
                    await self.create_clickup_webhook(team_id, app_host)
