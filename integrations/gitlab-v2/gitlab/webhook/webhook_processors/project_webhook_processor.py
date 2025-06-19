from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from typing import override, Dict, Any


class ProjectWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["project_create", "project_destroy"]
    hooks = ["Project Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project_id"]

        if payload["event_name"] == "project_destroy":
            logger.info(f"Deleted project {payload}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[self._parse_deleted_payload(payload)],
            )

        project = await self._gitlab_webhook_client.get_project(project_id)
        return WebhookEventRawResults(
            updated_raw_results=[project],
            deleted_raw_results=[],
        )

    @override
    async def validate_payload(self, payload: EventPayload) -> bool:
        return not ({"project_id"} - payload.keys())

    def _parse_deleted_payload(self, payload: EventPayload) -> Dict[str, Any]:
        """
        Parses the deleted payload to a map of the project's attributes.
        """
        return {
            "id": payload["project_id"],
            "name": payload["name"].split("/")[-1],
            "path": payload["path"].split("/")[-1],
            "path_with_namespace": payload["path_with_namespace"].split("/")[-1],
        }


#
