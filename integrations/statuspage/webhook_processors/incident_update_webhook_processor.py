from loguru import logger

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.base_webhook_processor import StatuspageBaseWebhookProcessor


class IncidentUpdateWebhookProcessor(StatuspageBaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        incident = event.payload.get("incident")
        return isinstance(incident, dict) and "incident_updates" in incident

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.INCIDENT_UPDATE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        incident = payload.get("incident")
        incident_updates = (
            incident.get("incident_updates") if isinstance(incident, dict) else None
        )
        return isinstance(incident_updates, list) and len(incident_updates) > 0

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        incident_updates = payload["incident"]["incident_updates"]
        logger.info(
            f"Processing Statuspage incident update webhook with {len(incident_updates)} updates"
        )

        return WebhookEventRawResults(
            updated_raw_results=incident_updates,
            deleted_raw_results=[],
        )
