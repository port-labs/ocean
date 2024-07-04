from typing import Any, AsyncGenerator
from httpx import Timeout
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 50


class ClickUpClient:
    def __init__(self, clickup_token: str) -> None:
        self.headers = {"Authorization": clickup_token}

        self.client = http_async_client
        self.client.headers.update(self.headers)
        self.client.timeout = Timeout(30)

    @staticmethod
    def _generate_base_req_params(
        max_results: int = PAGE_SIZE, start_at: int = 0
    ) -> dict[str, Any]:
        return {
            "page": start_at // max_results,
            "limit": max_results,
        }

    async def _get_paginated_teams(
        self, host: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get(f"{host}/api/v2/team", params=params)
        response.raise_for_status()
        return response.json()

    async def _get_paginated_spaces(
        self, host: str, team_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get(
            f"{host}/api/v2/team/{team_id}/space", params=params
        )
        response.raise_for_status()
        return response.json()

    async def _get_paginated_projects(
        self, host: str, space_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get(
            f"{host}/api/v2/space/{space_id}/list", params=params
        )
        response.raise_for_status()
        return response.json()

    async def _get_paginated_tasks(
        self, host: str, list_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get(
            f"{host}/api/v2/list/{list_id}/task", params=params
        )
        response.raise_for_status()
        return response.json()

    async def get_paginated_teams(
        self, host: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting teams from ClickUp")

        response = await self._get_paginated_teams(host, {})
        yield response["teams"]

    async def get_paginated_projects(
        self, host: str, team_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Getting projects from ClickUp for team {team_id}")

        response = await self._get_paginated_spaces(host, team_id, {})
        for space in response["spaces"]:
            projects = (await self._get_paginated_projects(host, space["id"], {}))[
                "lists"
            ]
            yield projects

    async def get_paginated_tasks(
        self, host: str, list_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Getting tasks from ClickUp for list {list_id}")

        params = self._generate_base_req_params()
        params["page"] = 0
        while True:
            tasks_response = (await self._get_paginated_tasks(host, list_id, params))[
                "tasks"
            ]
            if not tasks_response:
                break
            yield tasks_response
            params["page"] += 1

    async def create_events_webhook(
        self, host: str, app_host: str, team_id: str
    ) -> None:
        response = await self.client.post(
            f"{host}/api/v2/team/{team_id}/webhook",
            json={
                "endpoint": f"{app_host}/webhook",
                "events": ["taskCreated", "taskUpdated", "taskDeleted"],
            },
        )
        response.raise_for_status()
        logger.info("Webhook created successfully")

    async def get_single_task(self, host: str, task_id: str) -> dict[str, Any]:
        response = await self.client.get(f"{host}/api/v2/task/{task_id}")
        response.raise_for_status()
        return response.json()
