from typing import Any

from loguru import logger

from client import GitLabHandler
from choices import Entity


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

        entity = None
        payload = None

        match object_kind:
            case "issue":
                entity = Entity.ISSUE.value
                payload = await self.issue_handler(data)
            case "merge_request":
                entity = Entity.MERGE_REQUEST.value
                payload = await self.merge_request_handler(data)
            case _:
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

        entity = None
        payload = None

        match event_name:
            case event_name if event_name in self.GITLAB_PROJECT_EVENTS:
                entity = Entity.PROJECT.value
                payload = await self.system_hook_project_handler(data)
            case event_name if event_name in self.GITLAB_GROUP_EVENTS:
                entity = Entity.GROUP.value
                payload = await self.system_hook_group_handler(data)
            case _:
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
