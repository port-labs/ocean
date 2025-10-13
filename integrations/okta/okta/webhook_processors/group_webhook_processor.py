from typing import Any

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from okta.webhook_processors.base_webhook_processor import OktaBaseWebhookProcessor
from okta.clients.client_factory import OktaClientFactory
from okta.utils import ObjectKind, OktaEventType
from okta.core.exporters.group_exporter import OktaGroupExporter


class OktaGroupWebhookProcessor(OktaBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.GROUP]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event contains group-related events."""
        payload = event.payload
        events = payload["data"]["events"]

        for event_object in events:
            targets = event_object["target"]
            for target in targets:
                if target["type"] == "UserGroup" and target["id"]:
                    return True
        return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = OktaClientFactory.get_client()
        exporter = OktaGroupExporter(client)

        updated: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []

        for event_object in payload["data"]["events"]:
            event_type = event_object["eventType"]
            for target in event_object["target"]:
                if target["type"] == "UserGroup" and target["id"]:
                    group_id = target["id"]
                    if event_type == OktaEventType.GROUP_LIFECYCLE_DELETE.value:
                        deleted.append({"id": group_id})
                    else:
                        group = await exporter.get_resource(group_id)
                        updated.append(group)

        return WebhookEventRawResults(
            updated_raw_results=updated, deleted_raw_results=deleted
        )
