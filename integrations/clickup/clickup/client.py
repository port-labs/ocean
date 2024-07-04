from loguru import logger
from typing import Any, AsyncGenerator

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result


WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
WEBHOOK_EVENTS = [
    "listCreated",
    "listUpdated",
    "listDeleted",
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
    "taskCommentPosted",
    "taskCommentUpdated",
]


class ClickupClient:
    def __init__(self, clickup_personal_token: str) -> None:
        self.clickup_url = "https://api.clickup.com/api/v2"
        self.api_auth_header = {"Authorization": clickup_personal_token}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)

    async def create_webhook_events(self, app_host: str) -> None:
        async for team_batch in self.get_paginated_teams():
            for team in team_batch:
                await self._create_team_webhook_events(app_host, team["id"])

    async def _create_team_webhook_events(self, app_host: str, team_id: int) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhooks_response = await self.client.get(
            f"{self.clickup_url}/team/{team_id}/webhook"
        )
        webhooks_response.raise_for_status()
        webhooks = webhooks_response.json()

        existing_webhook = next(
            (
                webhook
                for webhook in webhooks["webhooks"]
                if webhook["endpoint"] == webhook_target_app_host
            ),
            None,
        )

        if existing_webhook:
            logger.info(
                f"Ocean real time reporting clickup webhook already exists [ID: {existing_webhook['id']}]"
            )
            return

        webhook_create_response = await self.client.post(
            f"{self.clickup_url}/team/{team_id}/webhook",
            json={
                "endpoint": webhook_target_app_host,
                "events": WEBHOOK_EVENTS,
            },
        )
        webhook_create_response.raise_for_status()
        webhook_create = webhook_create_response.json()
        logger.info(
            f"Ocean real time reporting clickup webhook created "
            f"[ID: {webhook_create['id']}, Team ID: {team_id}]"
        )

    async def get_paginated_teams(
        self, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        teams_response = await self.client.get(
            f"{self.clickup_url}/team", params=params
        )
        teams_response.raise_for_status()
        teams = teams_response.json()["teams"]
        yield teams

    async def _get_paginated_spaces(
        self, team_id: str, params: dict[str, Any] = {}
    ) -> list[dict[str, Any]]:
        spaces_response = await self.client.get(
            f"{self.clickup_url}/team/{team_id}/space", params=params
        )
        spaces_response.raise_for_status()
        return spaces_response.json()["spaces"]

    @cache_iterator_result()
    async def get_paginated_projects(
        self, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        # getting all teams so as to retrieve the spaces within each team, then using their
        # ids to get the projects (lists) within each space
        async for team_batch in self.get_paginated_teams(params):
            for team in team_batch:
                spaces = await self._get_paginated_spaces(team["id"], params)
                projects: list[dict[str, Any]] = []

                for space in spaces:
                    projects_response = await self.client.get(
                        f"{self.clickup_url}/space/{space['id']}/list", params=params
                    )
                    projects_response.raise_for_status()
                    # because the port-app-config uses the team ID to relate the projects to the teams
                    # we add the team ID to each project
                    # also, the clickup returns the datetime as a timestamp, so we convert it to a
                    # datetime object
                    projects.extend(
                        map(
                            lambda project: {
                                **project,
                                "__team_id": team["id"],
                            },
                            projects_response.json()["lists"],
                        )
                    )
                yield projects

    async def get_single_project(self, project_id: str) -> dict[str, Any]:
        # Clickup does not provide a direct way to get the team ID from a project (list), so instead
        # of directly getting the project, we get all the projects and filter by the project ID
        # using the result of the get_paginated_projects method which includes the team ID
        projects = self.get_paginated_projects()
        async for project_batch in projects:
            project = next(
                (project for project in project_batch if project["id"] == project_id),
                None,
            )
            if project:
                return project
        return {}

    async def get_paginated_issues(
        self, params: dict[str, Any] = {"page": 0}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        projects = self.get_paginated_projects(params)
        async for project_batch in projects:
            for project in project_batch:
                while True:
                    issues_response = await self.client.get(
                        f"{self.clickup_url}/list/{project['id']}/task", params=params
                    )
                    issues_response.raise_for_status()
                    issues = issues_response.json()
                    yield issues["tasks"]

                    if issues.get("last_page", False):
                        break

                    params["page"] += 1

    async def get_single_issue(self, issue_id: str) -> dict[str, Any]:
        issue_response = await self.client.get(f"{self.clickup_url}/task/{issue_id}")
        issue_response.raise_for_status()
        issue = issue_response.json()
        return issue
