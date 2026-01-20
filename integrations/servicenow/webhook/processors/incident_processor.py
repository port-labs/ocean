from typing import Any, List
from webhook.processors._base_processor import (
    _ServicenowAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import ObjectKind
from webhook.initialize_client import initialize_webhook_client


class IncidentWebhookProcessor(_ServicenowAbstractWebhookProcessor):
    """Incident webhook processor."""

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.INCIDENT]

    def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("sys_class_name") == ObjectKind.INCIDENT

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        sys_id = payload["sys_id"]

        updated_raw_results: List[dict[str, Any]] = []
        deleted_raw_results: List[dict[str, Any]] = []

        client = initialize_webhook_client()
        incident = await client.get_record_by_sys_id(ObjectKind.INCIDENT, sys_id)

        if incident:
            updated_raw_results.append(incident)
        else:
            deleted_raw_results.append(payload)

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
