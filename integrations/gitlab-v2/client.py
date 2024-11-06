import asyncio
import dateutil.parser as dt_parser

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


class GitLabHandler:
    def __init__(self) -> None:
        self.token = ocean.integration_config.get("gitlab_token")
        self.gitlab_baseurl = ocean.integration_config.get("gitlab_url")
        self.port_url = ocean.config.port.base_url
        self.client = http_async_client
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def fetch_data(self, endpoint: str) -> dict:
        url = f"{self.gitlab_baseurl}{endpoint}"

        resp = await self.client.get(url, headers=self.headers)
        if resp.status_code == 429:  # Rate Limiting
            message = resp.json().get("message", "")
            logger.error(f"{message}, retry will start in 5 minutes.")
            await asyncio.sleep(300)  # Sleep for 5 minutes
            await self.fetch_data(endpoint)

        if resp.status_code != 200:
            logger.error(
                f"Encountered an HTTP error with status code: {resp.status_code} and response text: {resp.text} while calling {endpoint}"
            )
            return []

        return resp.json()

    async def patch_entity(
        self, blueprint_identifier: str, entity_identifier: str, payload: dict
    ):
        port_headers = await ocean.port_client.auth.headers()
        url = f"{self.port_url}/v1/blueprints/{blueprint_identifier}/entities/{entity_identifier}"
        resp = await self.client.put(url, json=payload, headers=port_headers)
        if resp.status_code != 200:
            logger.error(
                f"Encountered an HTTP error with status code: {resp.status_code} and response text: {resp.text}"
            )

        return resp.json()

    async def parse_datetime(self, datetime_str: str) -> str:
        obj = dt_parser.parse(datetime_str)
        return obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    async def issue_handler(self, data: dict) -> None:
        """
        headers - X-Gitlab-Event: Issue Hook

        https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#issue-events
        """

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["id"]
        labels = [data["title"] for data in data["labels"]]
        payload = {
            "identifier": str(entity_id),
            "title": object_attributes["title"],
            "properties": {
                "link": object_attributes["url"],
                "description": object_attributes["description"],
                "createdAt": await self.parse_datetime(object_attributes["created_at"]),
                "updatedAt": await self.parse_datetime(object_attributes["updated_at"]),
                "creator": data["user"]["name"],
                "status": object_attributes["state"],
                "labels": ", ".join(labels),
            },
            "relations": {"service": str(object_attributes["project_id"])},
        }

        await self.patch_entity("gitlabIssue", entity_id, payload)

    async def merge_request_handler(self, data: dict) -> None:
        """
        X-Gitlab-Event: Merge Request Hook

        https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#merge-request-events
        """

        object_attributes = data["object_attributes"]
        entity_id = object_attributes["id"]
        reviewers = [data["name"] for data in data.get("reviewers", [])]

        payload = {
            "identifier": str(entity_id),
            "title": object_attributes["title"],
            "properties": {
                "creator": data["user"]["name"],
                "status": object_attributes["state"],
                "createdAt": await self.parse_datetime(object_attributes["created_at"]),
                "updatedAt": await self.parse_datetime(object_attributes["updated_at"]),
                "link": object_attributes["url"],
                "reviewers": ", ".join(reviewers),
            },
            "relations": {"service": str(data["project"]["id"])},
        }

        await self.patch_entity("gitlabMergeRequest", entity_id, payload)

    async def webhook_handler(self, data: dict) -> None:
        object_kind = data["object_kind"]
        if object_kind == "issue":
            await self.issue_handler(data)
        elif object_kind == "merge_request":
            await self.merge_request_handler(data)

    async def project_handler(self, data: dict) -> None:
        entity_id = data["group_id"]
        payload = {
            "identifier": str(entity_id),
            "title": data["name"],
            "properties": {
                "namespace": data["path_with_namespace"],
            },
        }

        await self.patch_entity("project", entity_id, payload)

    async def group_handler(self, data: dict) -> None:
        entity_id = data["project_id"]
        payload = {
            "identifier": str(entity_id),
            "title": data["name"],
            "properties": {},
        }

        await self.patch_entity("gitlabGroup", entity_id, payload)

    async def system_hook_handler(self, data: dict) -> None:
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
