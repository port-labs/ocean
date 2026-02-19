from loguru import logger
from initialize_client import create_jira_client
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class VersionWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("jira:version_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.VERSION]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "version" in payload and "id" in payload.get("version", {})

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_jira_client()
        webhook_event = payload.get("webhookEvent", "")
        version = payload["version"]
        version_id = str(version["id"])

        if webhook_event == "jira:version_deleted":
            logger.info(f"Version {version_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[version],
            )

        logger.debug(f"Fetching version with id: {version_id}")
        item = await client.get_single_version(version_id)

        if not item:
            logger.warning(f"Failed to retrieve version {version_id}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[item],
            deleted_raw_results=[],
        )
