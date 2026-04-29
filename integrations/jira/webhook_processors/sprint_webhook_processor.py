from loguru import logger

from initialize_client import get_or_create_jira_client
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


class SprintWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("sprint_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.SPRINT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        sprint = payload.get("sprint")
        if not isinstance(sprint, dict):
            return False
        return sprint.get("id") is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent", "")
        sprint = payload["sprint"]
        sprint_id: int = sprint["id"]

        if webhook_event == "sprint_deleted":
            logger.info(f"Sprint {sprint_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[sprint],
            )

        client = get_or_create_jira_client()
        logger.debug(f"Fetching sprint with id: {sprint_id}")
        item = await client.get_single_sprint(sprint_id=sprint_id)

        if not item:
            logger.warning(
                f"Sprint {sprint_id} could not be retrieved after {webhook_event} event"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        logger.debug(f"Retrieved sprint {sprint_id}")
        return WebhookEventRawResults(
            updated_raw_results=[item],
            deleted_raw_results=[],
        )
