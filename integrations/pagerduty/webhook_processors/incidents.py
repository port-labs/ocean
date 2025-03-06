from clients.pagerduty import PagerDutyClient
from consts import INCIDENT_UPSERT_EVENTS
from kinds import Kinds
from webhook_processors.abstract import (
    PagerdutyAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class IncidentWebhookProcessor(PagerdutyAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.payload.get("event", {}).get("event_type") in INCIDENT_UPSERT_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.INCIDENTS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = PagerDutyClient.from_ocean_configuration()
        incident_id = payload.get("event", {}).get("data", {}).get("id")
        incident = await client.get_single_resource(
            object_type=Kinds.INCIDENTS, identifier=incident_id
        )
        enriched_incident = await client.enrich_incidents_with_analytics_data(
            [incident["incident"]] if incident.get("incident") else []
        )
        return WebhookEventRawResults(
            updated_raw_results=enriched_incident,
            deleted_raw_results=[],
        )
