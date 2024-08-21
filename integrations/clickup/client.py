import asyncio
import time
from typing import Any, AsyncGenerator, Optional, List, Dict
from httpx import HTTPStatusError, Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

MINIMUM_LIMIT_REMAINING = (
    1001  # The minimum limit returned in the headers before waiting
)
DEFAULT_SLEEP_TIME = 5  # The Default wait time when limit is hit
DEFAULT_SEMAPHORE_VALUE = 1000  # The default number of concurrent requests allowed
SEMAPHORE = asyncio.BoundedSemaphore(DEFAULT_SEMAPHORE_VALUE)
SEMAPHORE_UPDATED = False

TEAM_OBJECT = "__team"
WEBHOOK_EVENTS = [
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
    "listCreated",
    "listUpdated",
    "listDeleted",
    "spaceCreated",
    "spaceUpdated",
    "spaceDeleted",
]


class ClickupClient:
    """Clickup client to interact with Clickup API."""

    def __init__(
        self,
        clickup_url: str,
        clickup_token: str,
        is_archived: bool,
        workspace_ids: Optional[str] = None,
    ) -> None:
        self.clickup_token = clickup_token
        self.api_url = f"{clickup_url}/api/v2"
        self.client = http_async_client
        self.client.timeout = Timeout(60)
        self.is_archived = is_archived
        self.workspace_ids = (
            [ws_id.strip() for ws_id in workspace_ids.split(",")]
            if workspace_ids
            else []
        )

    @property
    def api_headers(self) -> dict[str, Any]:
        return {
            "Authorization": self.clickup_token,
            "Content-Type": "application/json",
        }

    async def _fetch_with_rate_limit_handling(
        self,
        url: str,
        method: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Sends an HTTP request to the ClickUp API with rate limit handling.
        The acceptable rate is described in the documentation provided by Clickup at
        https://clickup.com/api/developer-portal/rate-limits/ and the rate limit headers are described at
        https://rdrr.io/github/psolymos/clickrup/src/R/cu-ratelimit.R
        """
        global SEMAPHORE_UPDATED
        global SEMAPHORE
        global MINIMUM_LIMIT_REMAINING
        while True:
            async with SEMAPHORE:
                response = await self.client.request(
                    url=url,
                    method=method,
                    headers=self.api_headers,
                    params=params,
                    json=json_data,
                )
                try:
                    response.raise_for_status()
                    # Update semaphore based on the rate limit if not updated already
                    if not SEMAPHORE_UPDATED:
                        rate_limit = int(
                            response.headers.get(
                                "X-RateLimit-Limit", DEFAULT_SEMAPHORE_VALUE
                            )
                        )
                        SEMAPHORE = asyncio.BoundedSemaphore(int(rate_limit / 10))
                        MINIMUM_LIMIT_REMAINING = int((rate_limit / 10) + 1)
                        SEMAPHORE_UPDATED = True
                        logger.info(
                            f"Number of concurrent requests allowed adjusted to {int(rate_limit/10)} based on X-RateLimit-Limit header"
                        )
                    rate_limit_remaining = int(
                        response.headers.get("X-RateLimit-Remaining", 1)
                    )
                    rate_limit_reset = int(
                        response.headers.get("X-RateLimit-Reset", DEFAULT_SLEEP_TIME)
                    )
                    if rate_limit_remaining <= MINIMUM_LIMIT_REMAINING:
                        current_time = int(time.time())
                        wait_time = rate_limit_reset - current_time
                        logger.warning(
                            f"Approaching rate limit. Waiting for {wait_time} seconds to continue export. "
                            f"URL: {url}, Remaining: {rate_limit_remaining} "
                        )
                        await asyncio.sleep(wait_time)
                except KeyError as e:
                    logger.error(
                        f"Rate limit headers not found in response: {str(e)} for url {url}"
                    )
                except HTTPStatusError as e:
                    logger.error(
                        f"Got HTTP error to url: {url} with status code: {e.response.status_code} and response text: {e.response.text}"
                    )
                    raise
            return response

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send a request to the Clickup API with rate limiting."""
        response = await self._fetch_with_rate_limit_handling(
            url, method, params, json_data
        )
        return response.json()

    @cache_iterator_result()
    async def get_clickup_teams(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all Clickup teams."""
        teams = (await self._send_api_request(f"{self.api_url}/team")).get("teams", [])
        if self.workspace_ids:
            teams = [team for team in teams if team["id"] in self.workspace_ids]
        yield teams

    @cache_iterator_result()
    async def _get_spaces_in_team(
        self, team_id: str
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all spaces in a workspace."""
        yield (
            await self._send_api_request(
                f"{self.api_url}/team/{team_id}/space",
                {"is_archived": self.is_archived},
            )
        ).get("spaces", [])

    async def get_all_spaces(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all spaces across all teams."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                async for spaces in self._get_spaces_in_team(team.get("id")):
                    yield [{**space, TEAM_OBJECT: team} for space in spaces]

    @cache_iterator_result()
    async def _get_folders_in_space(
        self, space_id: str
    ) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all folders in a space."""
        yield (
            await self._send_api_request(
                f"{self.api_url}/space/{space_id}/folder",
                {"is_archived": self.is_archived},
            )
        ).get("folders")

    async def _fetch_projects(
        self, parent_type: str, parent_id: str
    ) -> List[dict[str, Any]]:
        """Fetch projects based on the parent type and id."""
        url = f"{self.api_url}/{parent_type}/{parent_id}/list"
        response = await self._send_api_request(url, {"is_archived": self.is_archived})
        return response.get("lists", [])

    async def get_all_projects(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all projects, both foldered and folderless."""
        async for teams in self.get_clickup_teams():
            for team in teams:
                async for spaces in self._get_spaces_in_team(team.get("id")):
                    for space in spaces:
                        folderless_projects = await self._fetch_projects(
                            "space", space.get("id")
                        )
                        yield [
                            {**project, TEAM_OBJECT: team}
                            for project in folderless_projects
                        ]
                        async for folders in self._get_folders_in_space(
                            space.get("id")
                        ):
                            for folder in folders:
                                projects = await self._fetch_projects(
                                    "folder", folder.get("id")
                                )
                                yield [
                                    {**project, TEAM_OBJECT: team}
                                    for project in projects
                                ]

    async def get_paginated_tasks(self) -> AsyncGenerator[List[dict[str, Any]], None]:
        """Get all tasks in a project."""
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

    async def get_single_space(
        self, space_id: str, team_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single space by space_id."""
        async for spaces in self._get_spaces_in_team(team_id):
            for space in spaces:
                if space["id"] == space_id:
                    return {**space, TEAM_OBJECT: {"id": team_id}}
        logger.warning(f"No matching space found for {space_id}")
        return None

    async def get_single_project(
        self, list_id: str, team_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single project by list_id."""
        response = await self._send_api_request(f"{self.api_url}/list/{list_id}")
        return {**response, TEAM_OBJECT: {"id": team_id}}

    async def get_single_task(self, task_id: str) -> dict[str, Any]:
        """Get a single task by task_id."""
        return await self._send_api_request(f"{self.api_url}/task/{task_id}")

    async def create_clickup_webhook(
        self, team_id: str, app_host: str
    ) -> Dict[str, Any]:
        """
        Create a new webhook for a given team.
        """
        response = await self._send_api_request(
            f"{self.api_url}/team/{team_id}/webhook",
            method="POST",
            json_data={
                "endpoint": f"{app_host}/integration/webhook",
                "events": WEBHOOK_EVENTS,
            },
        )
        logger.info("Webhook created successfully")
        return response

    async def get_clickup_webhooks(self, team_id: str) -> list[dict[str, Any]]:
        """
        Retrieve existing webhooks for a given team.
        """
        return (await self._send_api_request(f"{self.api_url}/team/{team_id}/webhook"))[
            "webhooks"
        ]
