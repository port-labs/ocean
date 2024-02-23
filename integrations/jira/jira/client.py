import typing
from typing import Any, AsyncGenerator

import httpx
from httpx import BasicAuth, Timeout
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

from jira.overrides import JiraResourceConfig

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"

WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "project_created",
    "project_updated",
    "project_deleted",
    "project_soft_deleted",
    "project_restored_deleted",
    "project_archived",
    "project_restored_archived",
    "sprint_created",
    "sprint_updated",
    "sprint_deleted",
    "sprint_started",
    "sprint_closed",
    "board_created",
    "board_updated",
    "board_deleted",
    "board_configuration_changed",
]


class JiraClient:
    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        self.jira_url = jira_url
        self.base_url = f"{self.jira_url}/rest/agile/1.0"
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.detail_base_url = f"{self.jira_rest_url}/api/3"
        self.jira_email = jira_email
        self.jira_token = jira_token

        self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)

        self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)

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
        data_key: str = "values",
        is_last_function: typing.Callable[
            [dict[str, Any]], bool
        ] = lambda response: response["isLast"],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {**self._generate_base_req_params(), **params}
        is_last = False
        logger.info(f"Making paginated request to {url} with params: {params}")
        while not is_last:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()
                values = response_data[data_key]
                yield values
                is_last = is_last_function(response_data)
                start = response_data["startAt"] + response_data["maxResults"]
                params = {**params, "startAt": start}
                logger.info(f"Next page startAt: {start}")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
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
            yield projects

    async def get_issues(
        self, board_id: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {}
        config = typing.cast(JiraResourceConfig, event.resource_config)

        if config.selector.jql:
            params["jql"] = config.selector.jql
            logger.info(f"Found JQL filter: {config.selector.jql}")

        async for issues in self._make_paginated_request(
            f"{self.base_url}/board/{board_id}/issue",
            params=params,
            data_key="issues",
            is_last_function=lambda response: response["startAt"]
            + response["maxResults"]
            >= response["total"],
        ):
            yield issues

    async def get_sprints(
        self, board_id: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for sprints in self._make_paginated_request(
            f"{self.base_url}/board/{board_id}/sprint"
        ):
            yield sprints

    async def get_boards(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for boards in self._make_paginated_request(f"{self.base_url}/board/"):
            yield boards

    async def get_single_item(self, url: str) -> dict[str, Any]:
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
