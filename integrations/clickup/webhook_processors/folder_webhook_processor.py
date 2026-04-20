from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from clickup.helpers.utils import ObjectKind
from clickup.clients.client_factory import create_clickup_client
from clickup.core.exporters import FolderExporter
from webhook_processors.clickup_abstract_webhook_processor import (
    ClickUpAbstractWebhookProcessor,
)
from webhook_processors.utils import FOLDER_EVENTS, WebhookEvent as ClickUpEvent


class FolderWebhookProcessor(ClickUpAbstractWebhookProcessor):
    """Processes folder-related webhook events from ClickUp."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        event_type = event.payload.get("event")
        if not isinstance(event_type, str):
            return False

        try:
            return ClickUpEvent(event_type) in FOLDER_EVENTS
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the folder webhook event."""
        event_type = payload.get("event", "")
        folder_id = str(payload.get("folder_id", ""))

        logger.info(f"Processing webhook event '{event_type}' for folder: {folder_id}")

        if event_type == ClickUpEvent.FOLDER_DELETED:
            logger.info(f"Folder {folder_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": folder_id}],
            )

        client = create_clickup_client()
        exporter = FolderExporter(client)
        folder_data = await exporter.get_single_resource(folder_id)

        if not folder_data:
            logger.warning(f"Folder {folder_id} not found, treating as deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": folder_id}],
            )

        return WebhookEventRawResults(
            updated_raw_results=[folder_data],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields."""
        return (
            isinstance(payload, dict) and "event" in payload and "folder_id" in payload
        )
