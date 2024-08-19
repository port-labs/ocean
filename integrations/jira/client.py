import typing
from typing import Any, AsyncGenerator, Literal

import httpx
from httpx import BasicAuth, Timeout
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

from integration import SprintState

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
REQUEST_TIMEOUT = 60


CREATE_UPDATE_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "project_created",
    "project_updated",
    "project_restored_deleted",
    "project_restored_archived",
    "sprint_created",
    "sprint_updated",
    "sprint_started",
    "sprint_closed",
    "board_created",
    "board_updated",
    "board_configuration_changed",
]

DELETE_WEBHOOK_EVENTS = [
    "jira:issue_deleted",
    "project_deleted",
    "project_soft_deleted",
    "project_archived",
    "sprint_deleted",
    "board_deleted",
]

WEBHOOK_EVENTS = [
    *CREATE_UPDATE_WEBHOOK_EVENTS,
    *DELETE_WEBHOOK_EVENTS,
]


class JiraClient:
    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        self.jira_url = jira_url
        self.agile_url = f"{self.jira_url}/rest/agile/1.0"
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.detail_base_url = f"{self.jira_rest_url}/api/3"

        self.jira_api_auth = BasicAuth(jira_email, jira_token)
        self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(REQUEST_TIMEOUT)

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = 50, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

    async def _make_paginated_request(
        self,
        url: str,
        params: dict[str, Any] = {},
        is_last_function: typing.Callable[
            [dict[str, Any]], bool
        ] = lambda response: response["isLast"],
    ) -> AsyncGenerator[dict[str, list[dict[str, Any]]], None]:
        params = {**self._generate_base_req_params(), **params}
        is_last = False
        logger.info(f"Making paginated request to {url} with params: {params}")
        while not is_last:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()
                yield response_data
                is_last = is_last_function(response_data)
                start = response_data["startAt"] + response_data["maxResults"]
                params = {**params, "startAt": start}
                logger.info(f"Next page startAt: {start}")
            except httpx.HTTPStatusError as e:
                # some Jira boards may not support sprints
                # we check for these and skip throwing an error for them

                if e.response.status_code == 400 and (
                    "support sprints" in e.response.json()["errorMessages"][0]
                ):
                    logger.warning(
                        f"Jira board with url {url} does not support sprints"
                    )
                    is_last = True
                    continue

                logger.error(
                    f"HTTP error with status code: {e.response.status_code}"
                    f" and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching Jira data {e}")
                raise
        logger.info("Finished paginated request")
        return

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self._make_paginated_request(
            f"{self.detail_base_url}/project/search"
        ):
            yield projects["values"]

    async def _get_issues_from_sprint(
        self, params: dict[str, str], sprint_state: SprintState
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        sprint_params = {"state": sprint_state}
        async for sprints in self.get_all_sprints(sprint_params):
            for sprint in sprints:
                async for issues in self._make_paginated_request(
                    f"{self.agile_url}/sprint/{sprint['id']}/issue",
                    params=params,
                    is_last_function=lambda response: response["startAt"]
                    + response["maxResults"]
                    >= response["total"],
                ):
                    yield issues["issues"]

    async def _get_issues_from_org(
        self, params: dict[str, str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for issues in self._make_paginated_request(
            f"{self.detail_base_url}/search",
            params=params,
            is_last_function=lambda response: response["startAt"]
            + response["maxResults"]
            >= response["total"],
        ):
            yield issues["issues"]

    async def get_all_issues(
        self,
        source: Literal["sprint", "all"],
        params: dict[str, Any] = {},
        sprintState: SprintState = "active",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Running syncing for issues from source {}".format(source))

        if source == "sprint":
            async for issues in self._get_issues_from_sprint(params, sprintState):
                yield issues
            return

        async for issues in self._get_issues_from_org(params):
            yield issues

    @cache_iterator_result()
    async def _get_sprints_from_board(
        self, board_id: int, params: dict[str, str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for sprints in self._make_paginated_request(
            f"{self.agile_url}/board/{board_id}/sprint", params=params
        ):
            yield sprints["values"]

    @cache_iterator_result()
    async def get_all_sprints(
        self, params: dict[str, str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for boards in self.get_all_boards():
            for board in boards:
                async for sprints in self._get_sprints_from_board(board["id"], params):
                    yield sprints

    @cache_iterator_result()
    async def get_all_boards(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for boards in self._make_paginated_request(f"{self.agile_url}/board/"):
            yield boards["values"]

    async def _get_single_item(self, url: str) -> dict[str, Any]:
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {url}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching Jira data {e}")
            raise

    async def get_single_project(self, project: str) -> dict[str, Any]:
        return await self._get_single_item(f"{self.detail_base_url}/project/{project}")

    async def get_single_issue(self, issue: str) -> dict[str, Any]:
        return await self._get_single_item(f"{self.agile_url}/issue/{issue}")

    async def get_single_sprint(self, sprint_id: int) -> dict[str, Any]:
        return await self._get_single_item(f"{self.agile_url}/sprint/{sprint_id}")

    async def get_single_board(self, board_id: int) -> dict[str, Any]:
        return await self._get_single_item(f"{self.agile_url}/board/{board_id}")

    async def create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhook_check_response = await self.client.get(f"{self.webhooks_url}")
        webhook_check_response.raise_for_status()
        webhook_check = webhook_check_response.json()

        for webhook in webhook_check:
            if webhook["url"] == webhook_target_app_host:
                logger.info("Ocean real time reporting webhook already exists")
                return

        body = {
            "name": f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            "url": webhook_target_app_host,
            "events": WEBHOOK_EVENTS,
        }

        webhook_create_response = await self.client.post(
            f"{self.webhooks_url}", json=body
        )
        webhook_create_response.raise_for_status()
        logger.info("Ocean real time reporting webhook created")
