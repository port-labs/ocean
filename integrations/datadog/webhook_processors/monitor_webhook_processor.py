from typing import Any
from initialize_client import init_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import ObjectKind


class MonitorWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MONITOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        dd_client = init_client()
        monitor = await dd_client.get_single_monitor(payload["alert_id"])

        return WebhookEventRawResults(
            updated_raw_results=[monitor] if monitor else [],
            deleted_raw_results=[],
        )

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "event_type" in payload and "alert_id" in payload
