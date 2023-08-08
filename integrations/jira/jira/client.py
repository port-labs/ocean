import typing
import httpx
import base64

from loguru import logger

from port_ocean.context.ocean import ocean

from jira.overrides import JiraPortAppConfig

PAGE_SIZE = 50
WEBHOOK_ID = "port-ocean-rt-webhook"


class JiraClient:
    def __init__(self, jira_url, jira_email, jira_token) -> None:
        self.jira_url = jira_url
        self.jira_email = jira_email
        self.jira_token = jira_token

        auth_message = f"{self.jira_email}:{self.jira_token}"
        auth_bytes = auth_message.encode("ascii")
        b64_bytes = base64.b64encode(auth_bytes)
        b64_message = b64_bytes.decode("ascii")
        auth_value = f"Basic {b64_message}"

        self.base_headers = {"Authorization": auth_value}

        self.api_url = f"{self.jira_url}/rest/api/3"
        self.webhooks_url = f"{self.jira_url}/rest/webhooks/1.0/webhook"

        self.client = httpx.AsyncClient(headers=self.base_headers)

    async def create_rt_issue_updates_webhook(self, app_host: str):
        # Check if the webhook exists
        webhook_check_response = await self.client.get(
            f"{self.webhooks_url}/{WEBHOOK_ID}"
        )
        if webhook_check_response.status_code == 404:
            # Webhook already exists
            return

        body = {}

        webhook_create_response = await self.client.post(
            f"{self.webhooks_url}", json=body
        )

    async def get_all_projects(self):
        project_response = await self.client.get(f"{self.api_url}/project")
        project_response.raise_for_status()

        return project_response.json()

    async def get_paginated_issues(self):
        config = typing.cast(
            JiraPortAppConfig,
            ocean.app.integration.port_app_config_handler.get_port_app_config(),
        )
        logger.info(config.selector.jql)
        logger.info(f"Getting issues from Jira")
        get_more_issues = True
        start_at = 0

        issue_len_response = await self.client.get(
            f"{self.api_url}/search?maxResults=0&startAt=0"
        )
        issue_len_response.raise_for_status()
        total_issues = issue_len_response.json()["total"]

        while get_more_issues:
            logger.info(f"Current query position: {start_at}/{total_issues}")
            issue_response = await self.client.get(
                f"{self.api_url}/search?maxResults={PAGE_SIZE}&startAt={start_at}"
            )
            issue_response.raise_for_status()
            issue_response_list = issue_response.json()["issues"]
            yield issue_response_list
            # Stop querying for more issues when the paginated response has a
            # lower number of results than our page size (meaning we reached the last page)
            get_more_issues = len(issue_response_list) == PAGE_SIZE
            start_at += PAGE_SIZE
