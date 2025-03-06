from loguru import logger
from clients.pagerduty import PagerDutyClient
from consts import SERVICE_DELETE_EVENTS, SERVICE_UPSERT_EVENTS
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


class ServiceWebhookProcessor(PagerdutyAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.payload.get("event", {}).get("event_type") in SERVICE_UPSERT_EVENTS
            or event.payload.get("event", {}).get("event_type") in SERVICE_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.SERVICES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = PagerDutyClient.from_ocean_configuration()
        service_id = payload.get("event", {}).get("data", {}).get("id")
        if payload.get("event", {}).get("event_type") in SERVICE_DELETE_EVENTS:
            logger.info(f"Service {service_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload.get("event", {}).get("data")],
            )
        logger.info(
            f"Got event for service {service_id}: {payload.get('event', {}).get('event_type')}"
        )
        response = await client.get_single_resource(
            object_type=Kinds.SERVICES, identifier=service_id
        )
        services = await client.update_oncall_users([response["service"]])

        return WebhookEventRawResults(
            updated_raw_results=services, deleted_raw_results=[]
        )
