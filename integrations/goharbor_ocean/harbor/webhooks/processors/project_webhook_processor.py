from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from harbor.clients.client_factory import HarborClientFactory
from harbor.core.exporters.project_exporter import HarborProjectExporter
from harbor.helpers.utils import ObjectKind
from harbor.webhooks.base import HarborAbstractBaseWebhookProcessor
from harbor.webhooks.events import HarborEventType


class ProjectWebhookProcessor(HarborAbstractBaseWebhookProcessor):
    """Process Harbor project webhook events.

    Handles quota events that affect projects:
    - QUOTA_EXCEED
    - QUOTA_WARNING
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if event affects projects."""
        event_type = event.payload.get("type")

        return event_type in [
            HarborEventType.QUOTA_EXCEED,
            HarborEventType.QUOTA_WARNING,
        ]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get resource kinds this event affects."""
        return [ObjectKind.PROJECT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate webhook payload structure."""
        required_fields = ["type", "event_data"]
        return all(field in payload for field in required_fields)

    async def handle_event(
        self,
        payload: EventPayload,
        resource: ResourceConfig,
    ) -> WebhookEventRawResults:
        """Process project webhook event and return updated project.

        For quota events, we fetch the latest project state to reflect
        updated quota information.
        """
        event_type = payload.get("type")
        event_data = payload.get("event_data", {})

        logger.info(f"Processing Harbor project webhook event: {event_type}")

        repository = event_data.get("repository", {})
        project_name = repository.get("namespace") or repository.get("name", "").split("/")[0]

        if not project_name:
            logger.warning("Could not extract project name from webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = HarborClientFactory.get_client()
        exporter = HarborProjectExporter(client)

        match event_type:
            case HarborEventType.QUOTA_EXCEED | HarborEventType.QUOTA_WARNING:
                try:
                    project = await exporter.get_resource(project_name)

                    logger.info(f"Successfully fetched updated project: {project_name}")

                    return WebhookEventRawResults(
                        updated_raw_results=[project],
                        deleted_raw_results=[],
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch project {project_name}: {e}")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

            case _:
                logger.warning(f"Unhandled event type: {event_type}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
