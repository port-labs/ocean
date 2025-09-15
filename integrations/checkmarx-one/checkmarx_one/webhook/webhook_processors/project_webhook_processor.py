from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from checkmarx_one.core.options import SingleProjectOptions
from checkmarx_one.exporter_factory import create_project_exporter
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType
from checkmarx_one.webhook.webhook_processors.abstract_webhook_processor import _CheckmarxOneAbstractWebhookProcessor


class ProjectWebhookProcessor(_CheckmarxOneAbstractWebhookProcessor):
    """Processes project-related webhook events from Checkmarx One."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required project fields."""
        return "ID" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is a project-related event."""
        return (
            event.headers.get("x-cx-webhook-event")
            == CheckmarxEventType.PROJECT_CREATED
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the project kind for this webhook processor."""
        return [ObjectKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the project webhook event and return the raw results."""

        project_id = payload["ID"]

        logger.info(f"Processing project: {project_id}")

        project_exporter = create_project_exporter()
        data_to_upsert = await project_exporter.get_resource(
            SingleProjectOptions(project_id=project_id)
        )

        logger.info(f"Processed project data for project: {project_id}")

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert],
            deleted_raw_results=[],
        )
