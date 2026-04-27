from loguru import logger
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import ReleaseEvents
from azure_devops.client.azure_devops_client import (
    AzureDevopsClient,
    RELEASE_PUBLISHER_ID,
)


class ReleaseWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.RELEASE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        release_id = payload.get("resource", {}).get("release", {}).get("id")
        return project_id is not None and release_id is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != RELEASE_PUBLISHER_ID:
                return False
            event_type = event.payload["eventType"]
            return bool(ReleaseEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        project_id = payload["resourceContainers"]["project"]["id"]
        release_id = payload["resource"]["release"]["id"]

        release = await client.get_release(project_id, release_id)
        if not release:
            logger.warning(
                f"Release with ID {release_id} not found in project {project_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[release],
            deleted_raw_results=[],
        )
