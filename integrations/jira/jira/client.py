import typing
import httpx
import base64

from loguru import logger

from port_ocean.context.ocean import ocean
from jira.overrides import JiraResourceConfig

from jira.overrides import JiraPortAppConfig
from port_ocean.context.event import event

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-RT-Webhook"

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
    def __init__(self, jira_url, jira_email, jira_token) -> None:
        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        auth_message = f"{self.jira_email}:{self.jira_token}"
        auth_bytes = auth_message.encode("ascii")
        b64_bytes = base64.b64encode(auth_bytes)
        b64_message = b64_bytes.decode("ascii")
        auth_value = f"Basic {b64_message}"

        self.base_headers = {"Authorization": auth_value}

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.client = httpx.AsyncClient(headers=self.base_headers)

    async def create_real_time_updates_webhook(self, app_host: str):
        webhook_target_app_host = f"{app_host}/integration/hook"
        webhook_check_response = await self.client.get(f"{self.webhooks_url}")
        webhook_check_response.raise_for_status()
        webhook_check = webhook_check_response.json()

        for webhook in webhook_check:
            if webhook["url"] == webhook_target_app_host:
                logger.info("Ocean real time reporting webhook already exists")
                return

        body = {
            "name": WEBHOOK_NAME,
            "url": webhook_target_app_host,
            "events": WEBHOOK_EVENTS,
            "filters": {"issue-related-events-section": ""},
        }

        webhook_create_response = await self.client.post(
            f"{self.webhooks_url}", json=body
        )
        webhook_create_response.raise_for_status()
        logger.info("Ocean real time reporting webhook created")

    async def get_all_projects(self):
        project_response = await self.client.get(f"{self.api_url}/project")
        project_response.raise_for_status()

        return project_response.json()

    async def get_paginated_issues(self):
        logger.info(f"Getting issues from Jira")
        get_more_issues = True

        params = {
            "maxResults": 0,
            "startAt": 0,
        }

        config = typing.cast(JiraResourceConfig, event.resource_config)

        if config.selector.jql:
            params["jql"] = config.selector.jql

        total_issues = (await self._get_paginated_issues(params))["total"]

        params["maxResults"] = PAGE_SIZE
        while get_more_issues:
            logger.info(f"Current query position: {params['startAt']}/{total_issues}")
            issue_response_list = (await self._get_paginated_issues(params))["issues"]
            yield issue_response_list
            # Stop querying for more issues when the paginated response has a
            # lower number of results than our page size (meaning we reached the last page)
            get_more_issues = len(issue_response_list) == PAGE_SIZE
            params["startAt"] += PAGE_SIZE

    async def _get_paginated_issues(self, params):
        issue_response = await self.client.get(f"{self.api_url}/search", params=params)
        issue_response.raise_for_status()
        return issue_response.json()
