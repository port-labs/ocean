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


class DockerWebhookProcessor(BaseJFrogWebhookProcessor):
    """Process JFrog Docker tag webhook events"""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is a Docker event"""
        event_type = event.payload.get("event_type", "")
        return event_type in ["pushed", "deleted"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds this processor handles"""
        return ["dockerImage"]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle Docker tag webhook event

        Event types:
        - pushed: Docker tag was pushed
        - deleted: Docker tag was deleted
        """
        event_type = payload.get("event_type", "")
        data = payload.get("data", {})

        # Extract repository, image name, and tag
        repo_key = data.get("repo_key", "")
        image_name = data.get("image_name", "")
        tag = data.get("tag", "")
        path = data.get("path", "")
        sha256 = data.get("digest", "")
        size = data.get("size", 0)

        full_name = f"{repo_key}/{image_name}:{tag}"

        logger.info(f"Handling Docker webhook event: {event_type} for image: {full_name}")

        # For deleted events, return deleted results
        if event_type == "deleted":
            if full_name:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"fullName": full_name}],
                )

        # For pushed events, return the Docker image data
        docker_image = {
            "name": image_name,
            "tag": tag,
            "repository": repo_key,
            "fullName": full_name,
            "path": path,
            "sha256": sha256,
            "size": size,
        }

        return WebhookEventRawResults(
            updated_raw_results=[docker_image],
            deleted_raw_results=[],
        )
