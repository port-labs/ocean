from typing import Any, Dict
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
            "push": ObjectKind.PROJECT,
            "tag_push": ObjectKind.PROJECT,
            "issue": ObjectKind.ISSUE,
            "merge_request": ObjectKind.MERGE_REQUEST,
            "pipeline": ObjectKind.PROJECT,
            "job": ObjectKind.PROJECT,
            "deployment": ObjectKind.PROJECT,
            "release": ObjectKind.PROJECT,
            "project_token": ObjectKind.PROJECT,
            "group_token": ObjectKind.GROUP,
        }
        self.events = [
            "push_events", "tag_push_events",
            "project_create", "project_update", "project_delete",
            "group_create", "group_update", "group_delete",
            "merge_request_events", "pipeline_events", "deployment_events",
            "note_events", "wiki_page_events",
            "issue_events", "feature_flag_events", "releases_events",
            "project_token_events", "group_token_events"
        ]

    async def handle_event(self, event_type: str, payload: Dict[str, Any]):
        kind = self.event_handlers.get(event_type)
        if kind:
            await self._update_resource(kind, payload)
        else:
            logger.warning(f"Unhandled event type: {event_type}")

    async def _update_resource(self, resource_type: ObjectKind, payload: Dict[str, Any]):
        response = None
        api_version = await self.gitlab_handler.get_resource_api_version(resource_type)

        match resource_type:
            case ObjectKind.PROJECT:
                if project_id := payload.get("project", {}).get("id"):
                    url = f"{self.gitlab_handler.api_url}/{api_version}/{resource_type.value}s/{project_id}"
                    response = await self.gitlab_handler.get_single_resource(url)
                    logger.info(f"Updated project resource with ID: {project_id}")

            case ObjectKind.ISSUE:
                project_id = payload.get("project", {}).get("id")
                if issue_id := payload.get("object_attributes", {}).get("id"):
                    url = f"{self.gitlab_handler.api_url}/{api_version}/{resource_type.value}s/{issue_id}"
                    response = await self.gitlab_handler.get_single_resource(url)
                    logger.info(f"Updated issue resource with ID: {issue_id} for project ID: {project_id}")

            case ObjectKind.MERGE_REQUEST:
                project_id = payload.get("project", {}).get("id")
                if merge_request_id := payload.get("object_attributes", {}).get("id"):
                    url = f"{self.gitlab_handler.api_url}/{api_version}/{resource_type.value}s/{merge_request_id}"
                    response = await self.gitlab_handler.get_single_resource(url)
                    logger.info(
                        f"Updated merge request resource with ID: {merge_request_id} for project ID: {project_id}")

            case ObjectKind.GROUP:
                if group_id := payload.get("group", {}).get("id"):
                    url = f"{self.gitlab_handler.api_url}/{api_version}/{resource_type.value}s/{group_id}"
                    response = await self.gitlab_handler.get_single_resource(url)
                    logger.info(f"Updated group resource with ID: {group_id}")

        if response is not None:
            resource = response.json()
            await ocean.register_raw(resource_type, resource)

    async def setup(self) -> None:
        path = "/hooks"
        payload = {
            "url": WEBHOOK_URL,
            "events": self.events,
            "enable_ssl_verification": True,
        }

        try:
            await self.gitlab_handler.create_resource(path, payload)
            logger.info("Webhook setup completed")
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
