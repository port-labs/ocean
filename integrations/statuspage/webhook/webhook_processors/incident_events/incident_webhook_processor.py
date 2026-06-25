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


class IncidentWebhookProcessor(BaseIncidentWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return WebhookPayloadKey.INCIDENT in event.payload

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.INCIDENT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self.get_incident(payload) is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        incident = self.get_incident(payload)
        if incident is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing Statuspage incident webhook for incident: {incident.get('id')}"
        )

        return WebhookEventRawResults(
            updated_raw_results=[incident],
            deleted_raw_results=[],
        )
