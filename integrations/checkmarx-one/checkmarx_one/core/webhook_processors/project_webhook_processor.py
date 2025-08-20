from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from loguru import logger
from checkmarx_one.utils import CheckmarxEventType, ObjectKind
from checkmarx_one.exporter_factory import create_project_exporter
from checkmarx_one.core.options import SingleProjectOptions
from .abstract_webhook_processor import CheckmarxOneAbstractWebhookProcessor


class ProjectWebhookProcessor(CheckmarxOneAbstractWebhookProcessor):
    """Processes project-related webhook events from Checkmarx One."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is a project creation event."""
        event_type = event.payload.get("event_type", "")
        return event_type == CheckmarxEventType.PROJECT_CREATED

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the project webhook event and return the raw results."""
        logger.info("Processing project webhook event from Checkmarx One")

        # Extract project information from the webhook payload
        project_data = payload.get("project", {})
        if not project_data:
            logger.warning("No project data found in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        project_id = project_data.get("id")
        if not project_id:
            logger.warning("No project ID found in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        logger.info(f"Processing project: {project_id}")

        # Get the full project details using the project exporter
        project_exporter = create_project_exporter()
        try:
            options = SingleProjectOptions(project_id=project_id)
            full_project_data = await project_exporter.get_resource(options)
            if full_project_data:
                return WebhookEventRawResults(
                    updated_raw_results=[full_project_data],
                    deleted_raw_results=[],
                )
            else:
                logger.warning(
                    f"Could not retrieve project details for ID: {project_id}"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
        except Exception as e:
            logger.error(f"Error retrieving project details: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required project fields."""
        return "project" in payload and "event_type" in payload
