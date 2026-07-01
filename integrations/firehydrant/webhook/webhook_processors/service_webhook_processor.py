from typing import Any

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from init_client import init_client
from utils import ObjectKind
from webhook.webhook_processors.base_webhook_processor import (
    FirehydrantBaseWebhookProcessor,
)


class ServiceWebhookProcessor(FirehydrantBaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return "services" in event.payload.get("data", {})

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SERVICE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = init_client()
        # get_single_service returns a list (service enriched with incident milestones)
        updated: list[dict[str, Any]] = []
        for service in payload["data"]["services"]:
            service_data = await client.get_single_service(service_id=service["id"])
            updated.extend(service_data)
        return WebhookEventRawResults(
            updated_raw_results=updated,
            deleted_raw_results=[],
        )
