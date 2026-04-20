from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from clickup.helpers.utils import ObjectKind
from clickup.clients.client_factory import create_clickup_client
from clickup.core.exporters import SpaceExporter
from webhook_processors.clickup_abstract_webhook_processor import (
    ClickUpAbstractWebhookProcessor,
)
from webhook_processors.utils import SPACE_EVENTS, WebhookEvent as ClickUpEvent


class SpaceWebhookProcessor(ClickUpAbstractWebhookProcessor):
    """Processes space-related webhook events from ClickUp."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        event_type = event.payload.get("event")
        if not isinstance(event_type, str):
            return False

        try:
            return ClickUpEvent(event_type) in SPACE_EVENTS
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SPACE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the space webhook event."""
        event_type = payload.get("event", "")
        space_id = str(payload.get("space_id", ""))

        logger.info(f"Processing webhook event '{event_type}' for space: {space_id}")

        if event_type == ClickUpEvent.SPACE_DELETED:
            logger.info(f"Space {space_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": space_id}],
            )

        client = create_clickup_client()
        exporter = SpaceExporter(client)
        space_data = await exporter.get_single_resource(space_id)

        if not space_data:
            logger.warning(f"Space {space_id} not found, treating as deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": space_id}],
            )

        return WebhookEventRawResults(
            updated_raw_results=[space_data],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields."""
        return (
            isinstance(payload, dict) and "event" in payload and "space_id" in payload
        )
