from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.base_webhook_processor import BaseOctopusWebhookProcessor
from client import ObjectKind


class SpaceWebhookProcessor(BaseOctopusWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SPACE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = await self.get_client()
        event_data = payload["Payload"]["Event"]
        space_id = event_data["SpaceId"]

        if event_data.get("Category") == "Deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"Id": space_id}],
            )

        space_data = await client.get_single_space(space_id)
        return WebhookEventRawResults(
            updated_raw_results=[space_data],
            deleted_raw_results=[],
        )
