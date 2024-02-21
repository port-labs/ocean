import typing
from typing import Any, AsyncGenerator

from httpx import Timeout, BasicAuth
from jira.overrides import JiraResourceConfig
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

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
]


class JiraClient:
    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = 0, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

    async def _get_paginated_projects(self, params: dict[str, Any]) -> dict[str, Any]:
        project_response = await self.client.get(
            f"{self.api_url}/project/search", params=params
        )
        project_response.raise_for_status()
        return project_response.json()

    async def _get_paginated_issues(self, params: dict[str, Any]) -> dict[str, Any]:
        issue_response = await self.client.get(f"{self.api_url}/search", params=params)
        issue_response.raise_for_status()
        return issue_response.json()

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

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        project_response = await self.client.get(
            f"{self.api_url}/project/{project_key}"
        )
        project_response.raise_for_status()
        return project_response.json()

    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Jira")

        params = self._generate_base_req_params()

        total_projects = (await self._get_paginated_projects(params))["total"]

        if total_projects == 0:
            logger.warning(
                "Project query returned 0 projects, did you provide the correct Jira API credentials?"
            )

        params["maxResults"] = PAGE_SIZE
        while params["startAt"] <= total_projects:
            logger.info(f"Current query position: {params['startAt']}/{total_projects}")
            project_response_list = (await self._get_paginated_projects(params))[
                "values"
            ]
            yield project_response_list
            params["startAt"] += PAGE_SIZE

    async def get_single_issue(self, issue_key: str) -> dict[str, Any]:
        issue_response = await self.client.get(f"{self.api_url}/issue/{issue_key}")
        issue_response.raise_for_status()
        return issue_response.json()

    async def get_paginated_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Jira")

        params = self._generate_base_req_params()

        config = typing.cast(JiraResourceConfig, event.resource_config)

        if config.selector.jql:
            params["jql"] = config.selector.jql
            logger.info(f"Found JQL filter: {config.selector.jql}")

        total_issues = (await self._get_paginated_issues(params))["total"]

        if total_issues == 0:
            logger.warning(
                "Issue query returned 0 issues, did you provide the correct Jira API credentials and JQL query?"
            )

        params["maxResults"] = PAGE_SIZE
        while params["startAt"] <= total_issues:
            logger.info(f"Current query position: {params['startAt']}/{total_issues}")
            issue_response_list = (await self._get_paginated_issues(params))["issues"]
            yield issue_response_list
            params["startAt"] += PAGE_SIZE
