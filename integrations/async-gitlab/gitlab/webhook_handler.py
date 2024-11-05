from typing import Any, Dict
from functools import partial
from loguru import logger
from port_ocean.context.ocean import ocean
from gitlab.helpers.utils import ObjectKind
from gitlab.client import GitLabClient

WEBHOOK_SECRET = ocean.integration_config.get('webhook_secret')
SECRET_LENGTH = 32
WEBHOOK_URL = ocean.integration_config.get('app_host')

class WebhookHandler:
    def __init__(self) -> None:
        self.gitlab_handler = GitLabClient.create_from_ocean_config()
        self.event_handlers = {
            "push": partial(self._update_project),
            "tag_push": partial(self._update_project),
            "issue": partial(self._update_issue),
            "merge_request": partial(self._update_merge_request),
            "pipeline": partial(self._update_project),
            "job": partial(self._update_project),
            "deployment": partial(self._update_project),
            "release": partial(self._update_project),
            "project_token": partial(self._update_project),
            "group_token": partial(self._update_group),
        }

    async def handle_event(self, event_type: str, payload: Dict[str, Any]):
        handler = self.event_handlers.get(event_type)
        if handler:
            await handler(payload)
        else:
            logger.warning(f"Unhandled event type: {event_type}")

    async def _update_project(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            await self.gitlab_handler.update_resource(str(project_id), ObjectKind.PROJECT)
        pass

    async def _update_issue(self, payload: Dict[str, Any]):
        issue_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if issue_id and project_id:
            await self.gitlab_handler.update_resource(str(issue_id), ObjectKind.ISSUE)
        pass

    async def _update_merge_request(self, payload: Dict[str, Any]):
        merge_request_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if merge_request_id and project_id:
            await self.gitlab_handler.update_resource(str(merge_request_id), ObjectKind.MERGE_REQUEST)
        pass

    async def _update_group(self, payload: Dict[str, Any]):
        group_id = payload.get("group", {}).get("id")
        if group_id:
            await self.gitlab_handler.update_resource(str(group_id), ObjectKind.GROUP)
        pass
