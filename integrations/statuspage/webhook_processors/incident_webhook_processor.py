from loguru import logger

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.base_webhook_processor import StatuspageBaseWebhookProcessor


class IncidentWebhookProcessor(StatuspageBaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return "incident" in event.payload

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.INCIDENT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload.get("incident"), dict)

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        incident = payload["incident"]
        logger.info(
            f"Processing Statuspage incident webhook for incident: {incident.get('id')}"
        )

        return WebhookEventRawResults(
            updated_raw_results=[incident],
            deleted_raw_results=[],
        )
