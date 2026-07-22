from typing import cast
from clients.pagerduty import PagerDutyClient
from consts import INCIDENT_UPSERT_EVENTS
from kinds import Kinds
from integration import PagerdutyIncidentResourceConfig
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

    async def validate_payload(self, payload: EventPayload) -> bool:
        return bool(payload.get("event", {}).get("data", {}).get("id"))

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = PagerDutyClient.from_ocean_configuration()
        incident_id = payload["event"]["data"]["id"]

        data = await client.get_single_resource(
            object_type=Kinds.INCIDENTS, identifier=incident_id
        )
        incidents = [data["incident"]] if data.get("incident") else []

        selector = cast(PagerdutyIncidentResourceConfig, resource_config).selector
        if selector.incident_analytics:
            incidents = await client.enrich_incidents_with_analytics_data(incidents)

        if selector.include_custom_fields:
            incidents = await client.enrich_entities_with_custom_fields(
                incidents, Kinds.INCIDENTS
            )

        return WebhookEventRawResults(
            updated_raw_results=incidents,
            deleted_raw_results=[],
        )
