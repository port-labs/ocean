from typing import Any

from loguru import logger
from aiolimiter import AsyncLimiter

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from choices import Endpoint, Entity


class GitLabHandler:
    def __init__(self) -> None:
        self.client = http_async_client
        self.token = ocean.integration_config.get("gitlab_token")
        self.gitlab_baseurl = ocean.integration_config.get("gitlab_url")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def get_limiter(self, endpoint: str) -> AsyncLimiter:
        if endpoint == Endpoint.GROUP.value:
            rate_limit = ocean.integration_config.get("group_ratelimit", 200)
        elif endpoint == Endpoint.PROJECT.value:
            rate_limit = ocean.integration_config.get("project_ratelimit", 200)
        elif endpoint == Endpoint.MERGE_REQUEST.value:
            rate_limit = ocean.integration_config.get("mergerequest_ratelimit", 200)
        else:
            rate_limit = ocean.integration_config.get("issue_ratelimit", 200)

        return AsyncLimiter(0.8 * rate_limit)

    async def get_gitlab_data(self, url):
        self.token = ocean.integration_config.get("gitlab_token")
        self.gitlab_baseurl = ocean.integration_config.get("gitlab_url")

        headers = {"Authorization": f"Bearer {self.token}"}
        resp = await self.client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(
                f"Encountered an HTTP error with status code: {resp.status_code} and response text: {resp.text} while calling {url}"
            )
            return []

        return resp.json()

    async def fetch_data(self, endpoint: str) -> list[dict[str, Any]]:
        url = f"{self.gitlab_baseurl}{endpoint}"

        limiter = await self.get_limiter(endpoint)
        async with limiter:
            result = await self.get_gitlab_data(url)

            if endpoint == Endpoint.GROUP.value:
                for group_data in result:
                    group_id = group_data["id"]
                    await self.update_webhook(group_id)

            return result

    async def update_webhook(self, group_id: str) -> None:
        webhook_name = ocean.integration_config.get("webhook_name")
        webhook_secret = ocean.integration_config.get("webhook_secret")
        base_url = ocean.integration_config.get("base_url")
        webhook_payload = {
            "name": webhook_name,
            "url": f"{base_url}/integration/webhook",
            "custom_headers": [{"key": "port-headers", "value": webhook_secret}],
            "issues_events": True,
            "merge_requests_events": True,
        }
        url = f"{self.gitlab_baseurl}/groups/{group_id}/hooks"

        result = await self.get_gitlab_data(url)
        port_hook = next(
            (item for item in result if item["name"] == webhook_name), None
        )
        if not port_hook:
            await self.client.post(url, headers=self.headers, json=webhook_payload)

    async def issue_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        object_attributes = data["object_attributes"]
        entity_id = object_attributes["iid"]
        project_id = data["project"]["id"]

        url = f"{self.gitlab_baseurl}/projects/{project_id}/issues/{entity_id}"
        return await self.get_gitlab_data(url)

    async def merge_request_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        object_attributes = data["object_attributes"]
        entity_id = object_attributes["iid"]
        project_id = data["project"]["id"]

        url = f"{self.gitlab_baseurl}/projects/{project_id}/merge_requests/{entity_id}"
        return await self.get_gitlab_data(url)

    async def webhook_handler(self, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        object_kind = data["object_kind"]
        if object_kind == "issue":
            entity = Entity.ISSUE.value
            payload = await self.issue_handler(data)
        elif object_kind == "merge_request":
            entity = Entity.MERGE_REQUEST.value
            payload = await self.merge_request_handler(data)

        return entity, payload

    async def project_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        project_id = data["project_id"]
        url = f"{self.gitlab_baseurl}/projects/{project_id}"
        return await self.get_gitlab_data(url)

    async def group_handler(self, data: dict[str, Any]) -> dict[str, Any]:
        group_id = data["group_id"]
        url = f"{self.gitlab_baseurl}/groups/{group_id}"
        return await self.get_gitlab_data(url)

    async def system_hook_handler(
        self, data: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        event_name = data["event_name"]
        if event_name in [
            "project_create",
            "project_destroy",
            "project_rename",
            "project_update",
        ]:
            entity = Entity.PROJECT.value
            payload = await self.project_handler(data)
        elif event_name in ["group_create", "group_destroy", "group_rename"]:
            entity = Entity.GROUP.value
            payload = await self.group_handler(data)

        return entity, payload
