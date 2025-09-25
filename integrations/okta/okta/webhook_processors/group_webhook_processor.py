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
from loguru import logger


class OktaGroupWebhookProcessor(OktaBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.GROUP]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = OktaClientFactory.get_client()
        exporter = OktaGroupExporter(client)

        updated: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []

        for event_object in payload.get("data", {}).get("events", []):
            event_type = event_object.get("eventType", "")
            for target in event_object.get("target", []):
                if target.get("type") == "UserGroup" and target.get("id"):
                    group_id = target["id"]
                    if event_type == OktaEventType.GROUP_LIFECYCLE_DELETE.value:
                        deleted.append({"id": group_id})
                    else:
                        group = await exporter.get_resource(group_id)
                        logger.warning(f"Group data retrieved: {group}")
                        updated.append(group)

        return WebhookEventRawResults(updated_raw_results=updated, deleted_raw_results=deleted)


