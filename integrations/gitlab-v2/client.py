from typing import Any
import dateutil.parser as dt_parser

from loguru import logger
from aiolimiter import AsyncLimiter

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from choices import Endpoint, Entity


class GitLabHandler:
    def __init__(self) -> None:
        self.client = http_async_client

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

    async def fetch_data(self, endpoint: str) -> list[dict[str, Any]]:
        token = ocean.integration_config.get("gitlab_token")
        gitlab_baseurl = ocean.integration_config.get("gitlab_url")

        self.headers = {"Authorization": f"Bearer {token}"}
        url = f"{gitlab_baseurl}{endpoint}"

        limiter = await self.get_limiter(endpoint)
        async with limiter:
            resp = await self.client.get(url, headers=self.headers)
            if resp.status_code != 200:
                logger.error(
                    f"Encountered an HTTP error with status code: {resp.status_code} and response text: {resp.text} while calling {endpoint}"
                )
                return []

            return resp.json()

    async def patch_entity(self, entity_type: str, payload: dict[str, Any]) -> None:
        await ocean.register_raw(entity_type, [payload])

    async def parse_datetime(self, datetime_str: str) -> str:
        obj = dt_parser.parse(datetime_str)
        return obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    async def issue_handler(self, data: dict[str, Any]) -> None:
        """
        https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#issue-events
        """

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["id"]
        labels = [data["title"] for data in data["labels"]]

        payload = {
            "id": entity_id,
            "title": object_attributes["title"],
            "web_url": object_attributes["url"],
            "description": object_attributes["description"],
            "created_at": await self.parse_datetime(object_attributes["created_at"]),
            "updated_at": await self.parse_datetime(object_attributes["updated_at"]),
            "author": data["user"],
            "state": object_attributes["state"],
            "labels": labels,
            "project_id": object_attributes["project_id"],
        }

        closed_at = object_attributes.get("closed_at")
        if closed_at:
            payload["closed_at"] = await self.parse_datetime(closed_at)

        await self.patch_entity(Entity.ISSUE.value, payload)

    async def merge_request_handler(self, data: dict[str, Any]) -> None:
        """
        https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#merge-request-events
        """

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["id"]

        payload = {
            "id": entity_id,
            "title": object_attributes["title"],
            "author": {"name": data["user"]["name"]},
            "state": object_attributes["state"],
            "created_at": await self.parse_datetime(object_attributes["created_at"]),
            "updated_at": await self.parse_datetime(object_attributes["updated_at"]),
            "web_url": object_attributes["url"],
            "reviewers": data.get("reviewers", []),
            "project_id": data["project"]["id"],
        }

        await self.patch_entity(Entity.MERGE_REQUEST.value, payload)

    async def webhook_handler(self, data: dict[str, Any]) -> None:
        object_kind = data["object_kind"]
        if object_kind == "issue":
            await self.issue_handler(data)
        elif object_kind == "merge_request":
            await self.merge_request_handler(data)

    async def project_handler(self, data: dict[str, Any]) -> None:
        payload = {
            "id": data["project_id"],
            "name": data["name"],
            "description": data["path"],
            "path_with_namespace": data["path_with_namespace"]
        }

        await self.patch_entity(Entity.PROJECT.value, payload)

    async def group_handler(self, data: dict[str, Any]) -> None:
        payload = {
            "id": data["group_id"],
            "name": data["name"],
            "description": data["path"],
        }

        await self.patch_entity(Entity.GROUP.value, payload)

    async def system_hook_handler(self, data: dict[str, Any]) -> None:
        """
        https://docs.gitlab.com/ee/administration/system_hooks.html
        """

        event_name = data["event_name"]
        if event_name in [
            "project_create",
            "project_destroy",
            "project_rename",
            "project_update",
        ]:
            await self.project_handler(data)
        elif event_name in ["group_create", "group_destroy", "group_rename"]:
            await self.group_handler(data)
