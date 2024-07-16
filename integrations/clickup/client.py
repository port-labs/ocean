from enum import StrEnum
from typing import Any, AsyncGenerator, Optional
import httpx
from httpx import Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.context.event import event


class CacheKeys(StrEnum):
    TEAMS = "TEAMS"
    SPACES = "SPACES"
    TASKS = "TASKS"


CLICK_UP_WEBHOOK_EVENT = [
    "taskCreated",
    "taskUpdated",
    "taskPriorityUpdated",
    "taskStatusUpdated",
    "taskAssigneeUpdated",
    "taskDueDateUpdated",
    "taskTagUpdated",
    "taskMoved",
    "taskCommentPosted",
    "taskCommentUpdated",
    "taskTimeEstimateUpdated",
    "taskTimeTrackedUpdated",
    "listCreated",
    "listUpdated",
    "spaceCreated",
    "spaceUpdated",
]


class ClickUpClient:
    def __init__(self, clickup_token: str, host: str) -> None:
        self.api_url = f"{host}/api/v2"
        self.headers = {"Authorization": clickup_token}
        self.client = http_async_client
        self.client.headers.update(self.headers)
        self.client.timeout = Timeout(30)

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"Requesting ClickUp data for endpoint: {endpoint}")
        try:
            url = f"{self.api_url}/{endpoint}"
            logger.info(
                f"URL: {url}, Method: {method}, Params: {query_params}, Body: {json_data}"
            )
            response = await self.client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()
            logger.info(f"Successfully retrieved data for endpoint: {endpoint}")
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {endpoint}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {endpoint}: {str(e)}")
            raise

    async def get_teams(self) -> list[dict[str, Any]]:
        """
        Retrieve all teams from ClickUp.
        """
        return (await self.send_api_request("team"))["teams"]

    async def get_team_spaces(self, team_id: str) -> list[dict[str, Any]]:
        """
        Retrieve spaces for a given team.
        """
        return (await self.send_api_request(f"team/{team_id}/space"))["spaces"]

    async def get_space_lists(self, space_id: str) -> list[dict[str, Any]]:
        """
        Retrieve lists for a given space.
        """
        return (await self.send_api_request(f"space/{space_id}/list"))["lists"]

    async def get_spaces(self) -> list[dict[str, Any]]:
        """
        Retrieve all spaces across all teams, including lists within each space.
        """
        if cache := event.attributes.get(CacheKeys.SPACES):
            logger.info("Retrieving spaces data from cache")
            return cache

        teams = await self.get_teams()
        all_spaces = []
        for team in teams:
            team_spaces = await self.get_team_spaces(team["id"])
            for space in team_spaces:
                space_lists = await self.get_space_lists(space["id"])
                space["lists"] = space_lists
            all_spaces.extend(team_spaces)

        event.attributes[CacheKeys.SPACES] = all_spaces
        logger.info("Caching spaces data")

        return all_spaces

    async def _get_tasks(self, list_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Retrieve tasks for a given list with pagination support.
        """
        endpoint = f"list/{list_id}/task"
        response = await self.send_api_request(endpoint, query_params=params)
        return response

    async def get_paginated_tasks(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve paginated tasks for all lists.
        """
        spaces = await self.get_spaces()
        for space in spaces:
            for list_ in space.get("lists", []):
                params = {"page": 0}
                while True:
                    response = await self._get_tasks(list_["id"], params)
                    tasks = response["tasks"]
                    if not tasks:
                        break
                    yield tasks
                    if response["last_page"]:
                        break
                    params["page"] += 1

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """
        Retrieve a specific task by ID.
        """
        return await self.send_api_request(f"task/{task_id}")

    async def get_list(self, list_id: str) -> dict[str, Any]:
        """
        Retrieve a specific list by ID.
        """
        return await self.send_api_request(f"list/{list_id}")

    async def get_space(self, space_id: str) -> dict[str, Any]:
        """
        Retrieve a specific space by ID.
        """
        return await self.send_api_request(f"space/{space_id}")

    async def get_team(self, team_id: str) -> dict[str, Any]:
        """
        Retrieve a specific team by ID.
        """
        return await self.send_api_request(f"team/{team_id}")

    async def get_webhooks(self, team_id: str) -> list[dict[str, Any]]:
        """
        Retrieve existing webhooks for a given team.
        """
        return (await self.send_api_request(f"team/{team_id}/webhook"))["webhooks"]

    async def create_webhook(self, team_id: str, app_host: str) -> None:
        """
        Create a new webhook for a given team.
        """
        await self.send_api_request(
            f"team/{team_id}/webhook",
            method="POST",
            json_data={
                "endpoint": f"{app_host}/integration/webhook",
                "events": CLICK_UP_WEBHOOK_EVENT,
            },
        )
        logger.info("Webhook created successfully")
