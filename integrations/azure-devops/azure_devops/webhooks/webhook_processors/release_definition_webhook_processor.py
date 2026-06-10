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
    RELEASE_PUBLISHER_ID,
)


class ReleaseDefinitionWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.RELEASE_DEFINITION]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        release_id = payload.get("resource", {}).get("release", {}).get("id")
        resource_project = payload.get("resource", {}).get("project", {}).get("id")
        return (
            project_id is not None
            and release_id is not None
            and resource_project is not None
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != RELEASE_PUBLISHER_ID:
                return False
            event_type = event.payload["eventType"]
            return bool(ReleaseEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = self._get_client_for_webhook(payload)
        project_id = payload["resourceContainers"]["project"]["id"]
        release_id = payload["resource"]["release"]["id"]
        project = payload["resource"]["project"]

        release = await client.get_release(project_id, release_id)
        if not release:
            logger.warning(
                f"Release with ID {release_id} not found in project {project_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        definition_id = release["releaseDefinition"]["id"]
        definition = await client.get_release_definition(
            project_id, definition_id, project=project
        )
        if not definition:
            logger.warning(
                f"Release definition {definition_id} not found in project {project_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[definition],
            deleted_raw_results=[],
        )
