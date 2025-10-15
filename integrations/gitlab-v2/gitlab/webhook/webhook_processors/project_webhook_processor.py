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
import re


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
            deleted_project = self._parse_deleted_payload(payload)
            logger.info(f"Deleting project {deleted_project['path_with_namespace']}")

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[deleted_project],
            )

        project = await self._gitlab_webhook_client.get_project(project_id)
        return WebhookEventRawResults(
            updated_raw_results=[project],
            deleted_raw_results=[],
        )

    @override
    async def validate_payload(self, payload: EventPayload) -> bool:
        return not (
            {"project_id", "name", "path", "path_with_namespace"} - payload.keys()
        )

    def _strip_deleted_suffix(self, value: str) -> str:
        # Remove -deleted-<digits> or -<digits> at the end of the string
        return re.sub(r"(-deleted)?-\d+$", "", value)

    def _parse_deleted_payload(self, payload: EventPayload) -> Dict[str, Any]:
        """
        Parses the deleted payload to a map of the project's attributes.
        """
        return {
            "id": payload["project_id"],
            "name": self._strip_deleted_suffix(payload["name"]),
            "path": self._strip_deleted_suffix(payload["path"]),
            "path_with_namespace": self._strip_deleted_suffix(
                payload["path_with_namespace"]
            ),
        }
