from typing import Any

import httpx
from loguru import logger
from aiolimiter import AsyncLimiter

from port_ocean.utils import http_async_client
from choices import Endpoint, Entity, RequestType


class GitLabHandler:
    def __init__(
        self,
        host: str,
        gitlab_token: str,
        gitlab_url: str,
        webhook_secret: str,
        rate_limit: AsyncLimiter,
    ) -> None:
        self.client = http_async_client
        self.app_host = host
        self.gitlab_baseurl = gitlab_url
        self.token = gitlab_token
        self.webhook_secret = webhook_secret
        self.rate_limit = rate_limit
        self.headers = {"Authorization": f"Bearer {self.token}"}

    GITLAB_PROJECT_EVENTS = [
        "project_create",
        "project_destroy",
        "project_rename",
        "project_update",
    ]
    GITLAB_GROUP_EVENTS = ["group_create", "group_destroy", "group_rename"]

    async def call_gitlab(
        self,
        endpoint: str,
        request_type: str = RequestType.GET.value,
        payload: dict = {},
    ) -> list[dict[str, Any]] | dict[str, Any]:

        url = f"{self.gitlab_baseurl}{endpoint}"
        logger.info(f"Sending {request_type} request to Gitlab API: {url}")

        try:
            if request_type == RequestType.GET.value:
                response = await self.client.get(url=url, headers=self.headers)
            else:
                response = await self.client.post(
                    url=url, json=payload, headers=self.headers
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

    async def fetch_data(self, endpoint: str) -> list[dict[str, Any]]:
        async with self.rate_limit:
            result = await self.call_gitlab(endpoint)

            if endpoint == Endpoint.GROUP.value:
                for group_data in result:
                    group_id = group_data["id"]
                    await self.create_webhook(group_id)

            return result

    async def create_webhook(self, group_id: str) -> None:
        webhook_url = f"{self.app_host}/integration/webhook"
        webhook_payload = {
            "url": webhook_url,
            "custom_headers": [{"key": "port-headers", "value": self.webhook_secret}],
            "issues_events": True,
            "merge_requests_events": True,
        }
        endpoint = f"/groups/{group_id}/hooks"

        result = await self.call_gitlab(endpoint)
        port_hook = next((item for item in result if item["url"] == webhook_url), None)
        if not port_hook:
            await self.call_gitlab(
                endpoint,
                request_type=RequestType.POST.value,
                payload=webhook_payload,
            )

    async def issue_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing issue event webhook...")

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["iid"]
        project_id = data["project"]["id"]

        endpoint = f"/projects/{project_id}/issues/{entity_id}"
        return await self.call_gitlab(endpoint)

    async def merge_request_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing merge request event webhook...")

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["iid"]
        project_id = data["project"]["id"]

        endpoint = f"/projects/{project_id}/merge_requests/{entity_id}"
        return await self.call_gitlab(endpoint)

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

    async def system_hook_project_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing project event webhook...")

        project_id = data["project_id"]
        endpoint = f"/projects/{project_id}"
        return await self.call_gitlab(endpoint)

    async def system_hook_group_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("Processing group event webhook...")

        group_id = data["group_id"]
        endpoint = f"/groups/{group_id}"
        return await self.call_gitlab(endpoint)

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
