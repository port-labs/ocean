from integrations.pagerduty.clients.pagerduty import PagerDutyClient
from integrations.pagerduty.kinds import Kinds
from integrations.pagerduty.webhook_processors.abstract import (
    PagerdutyAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class ServiceWebhookProcessor(PagerdutyAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        client = PagerDutyClient.from_ocean_configuration()
        return (
            event.payload.get("event", {}).get("event_type")
            in client.service_upsert_events
            or event.payload.get("event", {}).get("event_type")
            in client.service_delete_events
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.SERVICES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = PagerDutyClient.from_ocean_configuration()
        if payload.get("event", {}).get("event_type") in client.service_delete_events:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload.get("event", {}).get("data")],
            )
        service_id = payload.get("event", {}).get("data", {}).get("id")
        response = await client.get_singular_from_pager_duty(
            object_type=Kinds.SERVICES, identifier=service_id
        )
        services = await client.update_oncall_users([response["service"]])

        return WebhookEventRawResults(
            updated_raw_results=services, deleted_raw_results=[]
        )
