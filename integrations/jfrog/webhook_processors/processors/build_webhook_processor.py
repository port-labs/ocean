from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from webhook_processors.processors._jfrog_abstract_webhook_processor import (
    BaseJFrogWebhookProcessor,
)


class BuildWebhookProcessor(BaseJFrogWebhookProcessor):
    """Process JFrog build webhook events"""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is a build event"""
        event_type = event.payload.get("event_type", "")
        return event_type in ["uploaded", "deleted", "promoted"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds this processor handles"""
        return ["build"]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle build webhook event

        Event types:
        - uploaded: Build was uploaded
        - deleted: Build was deleted
        - promoted: Build was promoted
        """
        event_type = payload.get("event_type", "")
        build_name = payload.get("build_name", "")
        build_number = payload.get("build_number", "")
        build_started = payload.get("build_started", "")

        logger.info(f"Handling build webhook event: {event_type} for build: {build_name}")

        # For deleted events, return deleted results
        if event_type == "deleted":
            if build_name:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"name": build_name}],
                )

        # For other events, return the build data
        build = {
            "name": build_name,
            "uri": f"/{build_name}",
            "lastStarted": build_started,
            "buildNumber": build_number,
        }

        return WebhookEventRawResults(
            updated_raw_results=[build],
            deleted_raw_results=[],
        )
