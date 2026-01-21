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


class ArtifactWebhookProcessor(BaseJFrogWebhookProcessor):
    """Process JFrog artifact webhook events"""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is an artifact event"""
        event_type = event.payload.get("event_type", "")
        return event_type in ["deployed", "deleted", "moved", "copied"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds this processor handles"""
        return ["artifact"]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle artifact webhook event

        Event types:
        - deployed: Artifact was deployed to repository
        - deleted: Artifact was deleted from repository
        - moved: Artifact was moved between repositories
        - copied: Artifact was copied to another repository
        """
        event_type = payload.get("event_type", "")
        data = payload.get("data", {})

        logger.info(f"Handling artifact webhook event: {event_type}")

        # For deleted events, return deleted results
        if event_type == "deleted":
            artifact_path = data.get("path", "")
            if artifact_path:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"path": artifact_path}],
                )

        # For other events, return the artifact data
        artifact = {
            "path": data.get("path", ""),
            "name": data.get("name", ""),
            "repo_key": data.get("repo_key", ""),
            "sha256": data.get("sha256", ""),
            "size": data.get("size", 0),
        }

        return WebhookEventRawResults(
            updated_raw_results=[artifact],
            deleted_raw_results=[],
        )
