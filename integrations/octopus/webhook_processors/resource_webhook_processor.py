from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.base_webhook_processor import BaseOctopusWebhookProcessor
from client import ObjectKind

TRACKED_EVENTS = [
    "spaces",
    "projects",
    "deployments",
    "releases",
    "machines",
]


class ResourceWebhookProcessor(BaseOctopusWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [
            ObjectKind.PROJECT,
            ObjectKind.DEPLOYMENT,
            ObjectKind.RELEASE,
            ObjectKind.MACHINE,
        ]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = await self.get_client()
        event_data = payload["Payload"]["Event"]
        space_id = event_data["SpaceId"]
        related_document_ids = event_data.get("RelatedDocumentIds", [])

        if event_data.get("Category") == "Deleted":
            resource_id = (
                event_data.get("ChangeDetails", {}).get("DocumentContext", {}).get("Id")
            )
            if resource_id:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"Id": resource_id}],
                )
            return WebhookEventRawResults([], [])

        results = []
        for resource_id in related_document_ids:
            resource_prefix = resource_id.split("-")[0].lower()
            if resource_prefix in TRACKED_EVENTS:
                try:
                    resource_data = await client.get_single_resource(
                        resource_prefix, resource_id, space_id
                    )
                    results.append(resource_data)
                except Exception as e:
                    logger.error(f"Failed to process resource {resource_id}: {e}")

        return WebhookEventRawResults(
            updated_raw_results=results,
            deleted_raw_results=[],
        )
