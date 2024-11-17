from typing import Any

import httpx
from loguru import logger
from aiolimiter import AsyncLimiter

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from choices import Entity


class GitLabHandler:
    def __init__(
        self,
        host: str | None,
        gitlab_token: str,
        gitlab_url: str,
        webhook_secret: str | None,
        rate_limit: AsyncLimiter,
    ) -> None:
        self.client = http_async_client
        self.app_host = host
        self.gitlab_baseurl = gitlab_url
        self.token = gitlab_token
        self.webhook_secret = webhook_secret
        self.rate_limit = rate_limit
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def send_gitlab_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: dict[str, Any] = {},
    ) -> list[dict[str, Any]] | dict[str, Any]:
        url = f"{self.gitlab_baseurl}/{endpoint}"
        logger.info(f"Sending {method} request to Gitlab API: {url}")

        try:
            response = await self.client.request(
                headers=self.headers,
                json=payload,
                method=method,
                url=url,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            return []
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a GET request to {url}"
            )
            return []

    async def create_webhook(self, group_id: str) -> None:
        webhook_url = f"{self.app_host}/integration/webhook"
        webhook_payload = {
            "url": webhook_url,
            "custom_headers": [{"key": "port-headers", "value": self.webhook_secret}],
            "issues_events": True,
            "merge_requests_events": True,
        }
        endpoint = f"groups/{group_id}/hooks"

        logger.info(f"Fetching hooks for group: {group_id}")
        result = await self.send_gitlab_api_request(endpoint)

        port_hook = next((item for item in result if item["url"] == webhook_url), None)
        if not port_hook:
            logger.info(f"Creating port hook for group: {group_id}")
            await self.send_gitlab_api_request(
                endpoint, method="POST", payload=webhook_payload
            )
        else:
            logger.info(
                f"Port hook already exist. Skipping port hook creation for group: {group_id}"
            )


class WebhookEventHandler:
    def __init__(self, gitlab_handler: GitLabHandler) -> None:
        self.gitlab_handler = gitlab_handler

    GITLAB_PROJECT_EVENTS = [
        "project_create",
        "project_destroy",
        "project_rename",
        "project_update",
    ]
    GITLAB_GROUP_EVENTS = ["group_create", "group_destroy", "group_rename"]

    async def group_hook_handler(
        self, data: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        object_kind = data["object_kind"]

        if object_kind == "issue":
            entity = Entity.ISSUE.value
            payload = await self.issue_handler(data)

        elif object_kind == "merge_request":
            entity = Entity.MERGE_REQUEST.value
            payload = await self.merge_request_handler(data)

        else:
            entity = None
            payload = None
            logger.error(f"Webhook group event: {object_kind} not processed...")

        return entity, payload

    async def merge_request_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing merge request event webhook...")

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["iid"]
        project_id = data["project"]["id"]

        endpoint = f"projects/{project_id}/merge_requests/{entity_id}"
        return await self.gitlab_handler.send_gitlab_api_request(endpoint)

    async def issue_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing issue event webhook...")

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["iid"]
        project_id = data["project"]["id"]

        endpoint = f"projects/{project_id}/issues/{entity_id}"
        return await self.gitlab_handler.send_gitlab_api_request(endpoint)

    async def system_hook_handler(
        self, data: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        event_name = data["event_name"]
        if event_name in self.GITLAB_PROJECT_EVENTS:
            entity = Entity.PROJECT.value
            payload = await self.system_hook_project_handler(data)

        elif event_name in self.GITLAB_GROUP_EVENTS:
            entity = Entity.GROUP.value
            payload = await self.system_hook_group_handler(data)

        else:
            entity = None
            payload = None
            logger.error(f"Webhook system event: {event_name} not processed...")

        return entity, payload

    async def system_hook_project_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing project event webhook...")

        project_id = data["project_id"]
        endpoint = f"projects/{project_id}"
        return await self.gitlab_handler.send_gitlab_api_request(endpoint)

    async def system_hook_group_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing group event webhook...")

        group_id = data["group_id"]
        endpoint = f"groups/{group_id}"
        return await self.gitlab_handler.send_gitlab_api_request(endpoint)


async def get_gitlab_handler(
    limiter: AsyncLimiter = AsyncLimiter(0.8 * 200),
) -> GitLabHandler:
    return GitLabHandler(
        host=ocean.integration_config.get("app_host"),
        gitlab_token=ocean.integration_config["gitlab_token"],
        gitlab_url=ocean.integration_config["gitlab_url"],
        webhook_secret=ocean.integration_config.get("webhook_secret"),
        rate_limit=limiter,
    )
