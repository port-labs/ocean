from loguru import logger
import httpx

from initialize_client import get_or_create_jira_client
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from jira.client import SPRINT_DELETED_EVENT, SPRINT_WEBHOOK_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class SprintWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent") in SPRINT_WEBHOOK_EVENTS

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

        if webhook_event == SPRINT_DELETED_EVENT:
            logger.info(f"Sprint {sprint_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[sprint],
            )

        client = get_or_create_jira_client()
        logger.debug(f"Fetching sprint with id: {sprint_id}")

        try:
            item = await client.get_single_sprint(sprint_id=sprint_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Sprint {sprint_id} not found after {webhook_event} event — "
                    f"sprint was likely deleted before processing completed"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[sprint],
                )
            raise

        logger.debug(f"Retrieved sprint {sprint_id}")
        return WebhookEventRawResults(
            updated_raw_results=[item],
            deleted_raw_results=[],
        )
