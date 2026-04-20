from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from clickup.helpers.utils import ObjectKind
from clickup.clients.client_factory import create_clickup_client
from clickup.core.exporters import TaskExporter
from webhook_processors.clickup_abstract_webhook_processor import (
    ClickUpAbstractWebhookProcessor,
)
from webhook_processors.utils import TASK_EVENTS, WebhookEvent as ClickUpEvent


class TaskWebhookProcessor(ClickUpAbstractWebhookProcessor):
    """Processes task-related webhook events from ClickUp."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        event_type = event.payload.get("event")
        if not isinstance(event_type, str):
            return False

        try:
            return ClickUpEvent(event_type) in TASK_EVENTS
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TASK]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the task webhook event."""
        event_type = payload.get("event", "")
        task_id = str(payload.get("task_id", ""))

        logger.info(f"Processing webhook event '{event_type}' for task: {task_id}")

        if event_type == ClickUpEvent.TASK_DELETED:
            logger.info(f"Task {task_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": task_id}],
            )

        client = create_clickup_client()
        exporter = TaskExporter(client)
        task_data = await exporter.get_single_resource(task_id)

        if not task_data:
            logger.warning(f"Task {task_id} not found, treating as deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": task_id}],
            )

        return WebhookEventRawResults(
            updated_raw_results=[task_data],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields."""
        return isinstance(payload, dict) and "event" in payload and "task_id" in payload
