from typing import Any, List
from webhook.processors._base_processor import (
    ServicenowAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import ObjectKind
from webhook.initialize_client import initialize_webhook_client


class UserGroupWebhookProcessor(ServicenowAbstractWebhookProcessor):
    """UserGroup webhook processor."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER_GROUP]

    def _should_process_event(self, event: WebhookEvent) -> bool:
        payload = event.payload
        return "roles" in payload and "manager" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        sys_id = payload["sys_id"]

        updated_raw_results: List[dict[str, Any]] = []
        deleted_raw_results: List[dict[str, Any]] = []

        client = initialize_webhook_client()
        user_group = await client.get_record_by_sys_id(ObjectKind.USER_GROUP, sys_id)

        if user_group:
            updated_raw_results.append(user_group)
        else:
            deleted_raw_results.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
