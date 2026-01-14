from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from harbor.clients.client_factory import HarborClientFactory
from harbor.core.exporters.artifact_exporter import HarborArtifactExporter
from harbor.helpers.utils import ObjectKind
from harbor.webhooks.base import HarborAbstractBaseWebhookProcessor
from harbor.webhooks.events import HarborEventType


class ArtifactWebhookProcessor(HarborAbstractBaseWebhookProcessor):
    """Process Harbor artifact webhook events."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        payload = event.payload
        event_type = payload.get("type")

        return event_type in [
            HarborEventType.PUSH_ARTIFACT,
            HarborEventType.DELETE_ARTIFACT,
            HarborEventType.SCANNING_COMPLETED,
        ]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get resource kinds this event affects."""
        return [ObjectKind.ARTIFACT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload structure.

        Args:
            payload: Event payload

        Returns:
            True if payload is valid
        """
        required_fields = ["type", "event_data"]
        return all(field in payload for field in required_fields)

    async def handle_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig,
    ) -> WebhookEventRawResults:
        """Process the webhook event and return affected resources.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Updated and deleted resources
        """
        event_type = payload.get("type")
        event_data = payload.get("event_data", {})

        logger.info(f"Processing Harbor webhook event: {event_type}")

        repository = event_data.get("repository", {})
        resources = event_data.get("resources", [])

        project_name = repository.get("namespace")
        repository_name = repository.get("name")

        if not project_name or not repository_name:
            logger.warning("Missing project or repository name in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = HarborClientFactory.get_client()
        exporter = HarborArtifactExporter(client)

        match event_type:
            case HarborEventType.PUSH_ARTIFACT | HarborEventType.SCANNING_COMPLETED:
                # fetch updated artifacts
                updated_artifacts = []

                for resource in resources:
                    artifact_digest = resource.get("digest")
                    if artifact_digest:
                        try:
                            artifact = await exporter.get_resource(
                                project_name=project_name,
                                repository_name=repository_name,
                                reference=artifact_digest,
                            )
                            updated_artifacts.append(artifact)
                        except Exception as e:
                            logger.warning(f"Failed to fetch artifact {artifact_digest}: {e}")

                return WebhookEventRawResults(
                    updated_raw_results=updated_artifacts,
                    deleted_raw_results=[],
                )

            case HarborEventType.DELETE_ARTIFACT:
                deleted_artifacts = [
                    {
                        "digest": resource.get("digest"),
                        "__project": project_name,
                        "__repository": repository_name,
                    }
                    for resource in resources
                ]

                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=deleted_artifacts,
                )

            case _:
                logger.warning(f"Unhandled event type: {event_type}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
