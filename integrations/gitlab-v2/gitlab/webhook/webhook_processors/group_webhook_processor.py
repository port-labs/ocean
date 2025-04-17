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


class GroupWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = [
        "group_create",
        "group_destroy",
        "subgroup_create",
        "subgroup_destroy",
    ]
    hooks = ["Subgroup Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.GROUP]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        group_id = payload["group_id"]
        event_name = payload["event_name"]
        full_path = payload["full_path"]

        logger.info(
            f"Handling {event_name} webhook event for group with ID '{group_id}' and full path '{full_path}'"
        )

        # For destroy events, no need to fetch group since it's already deleted
        if event_name in ("subgroup_destroy", "group_destroy"):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload],
            )

        # Only fetch group if needed
        group = await self._gitlab_webhook_client.get_group(group_id)
        return WebhookEventRawResults(
            updated_raw_results=[group] if group else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        # override the base class's validate_payload method
        return not ({"group_id", "full_path", "event_name"} - payload.keys())
