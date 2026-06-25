from loguru import logger

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook.consts import WebhookPayloadKey
from webhook.webhook_processors.incident_events.base_processor import (
    BaseIncidentWebhookProcessor,
)


class IncidentUpdateWebhookProcessor(BaseIncidentWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        incident = self.get_incident(event.payload)
        return incident is not None and WebhookPayloadKey.INCIDENT_UPDATES in incident

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.INCIDENT_UPDATE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        incident = self.get_incident(payload)
        if incident is None:
            return False

        incident_updates = incident.get(WebhookPayloadKey.INCIDENT_UPDATES)
        return isinstance(incident_updates, list) and len(incident_updates) > 0

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        incident = self.get_incident(payload)
        if incident is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        incident_updates = incident[WebhookPayloadKey.INCIDENT_UPDATES]
        logger.info(
            f"Processing Statuspage incident update webhook with {len(incident_updates)} updates"
        )

        return WebhookEventRawResults(
            updated_raw_results=incident_updates,
            deleted_raw_results=[],
        )
