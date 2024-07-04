from typing import Any, AsyncGenerator, List, Dict
from httpx import Timeout
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 50


class ClickUpClient:
    def __init__(self, clickup_host: str, clickup_token: str) -> None:
        self.clickup_host = clickup_host
        self.clickup_token = clickup_token

        self.headers = {"Authorization": self.clickup_token}

        self.client = http_async_client
        self.client.headers.update(self.headers)
        self.client.timeout = Timeout(30)

    @staticmethod
    def _generate_base_req_params(
            max_results: int = PAGE_SIZE, start_at: int = 0
    ) -> Dict[str, Any]:
        return {
            "page": start_at // max_results,
            "limit": max_results,
        }

    async def _get_paginated_teams(self, params: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get(
            f"{self.clickup_host}/api/v2/team", params=params
        )
        response.raise_for_status()
        return response.json()

    async def _get_paginated_spaces(
            self, team_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = await self.client.get(
            f"{self.clickup_host}/api/v2/team/{team_id}/space", params=params
        )
        response.raise_for_status()
        return response.json()

    async def _get_paginated_projects(
            self, space_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = await self.client.get(
            f"{self.clickup_host}/api/v2/space/{space_id}/list", params=params
        )
        response.raise_for_status()
        return response.json()

    async def _get_paginated_tasks(
            self, list_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = await self.client.get(
            f"{self.clickup_host}/api/v2/list/{list_id}/task", params=params
        )
        response.raise_for_status()
        return response.json()

    async def get_paginated_teams(
            self,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting teams from ClickUp")

        params = self._generate_base_req_params()

        total_teams = (await self._get_paginated_teams(params))["teams"]

        if not total_teams:
            logger.warning("Team query returned 0 teams")

        params["limit"] = PAGE_SIZE
        while params["page"] * PAGE_SIZE < len(total_teams):
            logger.info(
                f"Current query position: {params['page'] * PAGE_SIZE}/{len(total_teams)}"
            )
            teams_response = (await self._get_paginated_teams(params))["teams"]
            for team in teams_response:
                # Construct the URL for the team
                team_id = team["id"]
                space_id = team["space"]["id"] if "space" in team else "default_space"
                team["url"] = f"https://app.clickup.com/{team_id}/v/o/s/{space_id}"
            yield teams_response
            params["page"] += 1

    async def get_paginated_projects(
            self, team_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info(f"Getting projects from ClickUp for team {team_id}")

        params = self._generate_base_req_params()

        total_spaces = (await self._get_paginated_spaces(team_id, params))["spaces"]

        for space in total_spaces:
            space_id = space["id"]
            params["page"] = 0
            total_projects = (await self._get_paginated_projects(space_id, params))[
                "lists"
            ]

            if not total_projects:
                logger.warning(
                    f"Project query returned 0 projects for space {space_id}"
                )

            params["limit"] = PAGE_SIZE
            while params["page"] * PAGE_SIZE < len(total_projects):
                logger.info(
                    f"Current query position: {params['page'] * PAGE_SIZE}/{len(total_projects)}"
                )
                projects_response = (
                    await self._get_paginated_projects(space_id, params)
                )["lists"]
                yield projects_response
                params["page"] += 1

    async def get_paginated_tasks(
            self, list_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info(f"Getting tasks from ClickUp for list {list_id}")

        params = self._generate_base_req_params()

        total_tasks = (await self._get_paginated_tasks(list_id, params))["tasks"]

        if not total_tasks:
            logger.warning(f"Task query returned 0 tasks for list {list_id}")

        params["limit"] = PAGE_SIZE
        while params["page"] * PAGE_SIZE < len(total_tasks):
            logger.info(
                f"Current query position: {params['page'] * PAGE_SIZE}/{len(total_tasks)}"
            )
            tasks_response = (await self._get_paginated_tasks(list_id, params))["tasks"]
            for task in tasks_response:
                if "priority" in task and isinstance(task["priority"], dict):
                    task["priority"] = task["priority"]["priority"]
            yield tasks_response
            params["page"] += 1

    async def create_events_webhook(self, app_host: str) -> None:
        response = await self.client.post(
            f"{self.clickup_host}/api/v2/webhook",
            json={
                "endpoint": f"{app_host}/webhook",
                "events": ["taskCreated", "taskUpdated", "taskDeleted"],
            },
        )
        response.raise_for_status()
        logger.info("Webhook created successfully")

    async def get_single_task(self, task_id: str) -> Dict[str, Any]:
        response = await self.client.get(f"{self.clickup_host}/api/v2/task/{task_id}")
        response.raise_for_status()
        return response.json()
