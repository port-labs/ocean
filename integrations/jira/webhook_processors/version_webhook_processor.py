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
        return [Kinds.RELEASE]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        version = payload.get("version")
        return version is not None and (
            version.get("id") is not None or "projectId" in version
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        version = payload["version"]
        webhook_event = payload["webhookEvent"]
        client = create_jira_client()

        if webhook_event == "jira:version_deleted":
            logger.info(f"Received deletion event for version {version.get('id')}")
            updated_results = []
            # A merge fires as jira:version_deleted but includes a mergedTo field
            if "mergedTo" in payload:
                destination_version = await client.get_single_version(
                    str(payload["mergedTo"]["id"])
                )
                updated_results = [destination_version]
            return WebhookEventRawResults(
                updated_raw_results=updated_results,
                deleted_raw_results=[version],
            )

        enriched_version = await client.get_single_version(str(version["id"]))
        logger.info(
            f"Received upsert event for version {enriched_version['id']} in project {enriched_version['__projectKey']}"
        )
        return WebhookEventRawResults(
            updated_raw_results=[enriched_version],
            deleted_raw_results=[],
        )
