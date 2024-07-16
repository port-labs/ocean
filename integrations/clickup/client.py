from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

TEAMS_CACHE = "teams"
WEBHOOK_EVENTS = [
    "listCreated",
    "listUpdated",
    "listDeleted",
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
]
TEAM_ID_KEY = "__team_id"


class ClickupClient:
    def __init__(self, clickup_apikey: str) -> None:
        self.clickup_url = "https://api.clickup.com/api/v2"
        self.client = http_async_client
        self.client.headers.update({"Authorization": clickup_apikey})
        self.client.timeout = httpx.Timeout(30)

    async def get_teams(self) -> list[dict[str, Any]]:
        if cache := event.attributes.get(TEAMS_CACHE, []):
            return cache
        teams = await self._get_teams()
        event.attributes[TEAMS_CACHE] = teams
        return teams

    async def _get_teams(self) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/team"
        response = await self.client.get(url)
        response.raise_for_status()
        teams = response.json()["teams"]
        return teams

    async def create_webhook_events(self, app_host: str) -> None:
        for team in await self.get_teams():
            await self._create_team_webhook_events(app_host, team["id"])

    async def _create_team_webhook_events(self, app_host: str, team_id: int) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        try:
            response = await self.client.post(
                f"{self.clickup_url}/team/{team_id}/webhook",
                json={
                    "endpoint": webhook_target_app_host,
                    "events": WEBHOOK_EVENTS,
                },
            )
            response.raise_for_status()
            webhook = response.json()
            logger.info(
                "Ocean real time reporting clickup webhook created "
                f"[ID: {webhook['id']}, Team ID: {team_id}]"
            )
        except httpx.HTTPStatusError as e:
            # if you try to create webhook that already exist, you get status_code 400
            # and also the message "Webhook configuration already exists"
            if e.response.status_code == 400 and (
                "already exists" in e.response.json()["err"]
            ):
                logger.info(
                    "Ocean real-time reporting webhook already exist for "
                    f"Team ID: {team_id}"
                )
                return
            logger.error(
                f"HTTPStatusError {e} while creating webhook events for"
                f"Team ID: {team_id}"
            )
            return

        except httpx.HTTPError as e:
            logger.error(
                f"HTTPError {e} while creating webhook events for" f"Team ID: {team_id}"
            )
            return

    @cache_iterator_result()
    async def get_spaces(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        for team in await self.get_teams():
            yield await self._get_spaces(team["id"])

    async def _get_spaces(self, team_id: str) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/team/{team_id}/space"
        response = await self.client.get(url)
        response.raise_for_status()
        spaces = response.json()["spaces"]
        return [{**space, TEAM_ID_KEY: team_id} for space in spaces]

    @cache_iterator_result()
    async def get_folders(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for spaces in self.get_spaces():
            for space in spaces:
                yield await self._get_folders(space["id"], space[TEAM_ID_KEY])

    async def _get_folders(self, space_id: str, team_id: str) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/space/{space_id}/folder"
        response = await self.client.get(url)
        response.raise_for_status()
        folders = response.json()["folders"]
        return [{**folder, TEAM_ID_KEY: team_id} for folder in folders]

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for folders in self.get_folders():
            for folder in folders:
                yield await self._get_projects(folder["id"], folder[TEAM_ID_KEY])

    async def _get_projects(self, folder_id: str, team_id: str) -> list[dict[str, Any]]:
        url = f"{self.clickup_url}/folder/{folder_id}/list"
        response = await self.client.get(url)
        response.raise_for_status()
        projects = response.json()["lists"]
        return [{**project, TEAM_ID_KEY: team_id} for project in projects]

    async def get_single_project(self, project_id: str) -> dict[str, Any]:
        response = await self.client.get(f"{self.clickup_url}/list/{project_id}")
        response.raise_for_status()
        return response.json()

    async def get_paginated_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_projects():
            for project in projects:
                async for issues in self._get_issues(project["id"]):
                    yield issues

    async def _get_issues(
        self, project_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.clickup_url}/list/{project_id}/task"
        params = {"page": 0}
        last_page = False
        while not last_page:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            tasks = response.json()["tasks"]
            yield tasks
            last_page = not tasks
            params["page"] += 1

    async def get_single_issue(self, issue_id: str) -> dict[str, Any]:
        response = await self.client.get(f"{self.clickup_url}/task/{issue_id}")
        response.raise_for_status()
        return response.json()
