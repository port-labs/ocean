from webhook_processors.abstract import LinearAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from linear.client import LinearClient
from kinds import ObjectKind
from loguru import logger


class IssueWebhookProcessor(LinearAbstractWebhookProcessor):
    """Processes issue-related webhook events from Linear."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event header contains required Issue event type."""

        return event.headers.get("linear-event") == "Issue"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the issue webhook event and return the raw results."""
        client = LinearClient.create_from_ocean_configuration()
        event_data = payload["data"]

        logger.info(f'Processing webhook event for issue: {event_data["identifier"]}')
        data_to_update = await client.get_single_issue(event_data["identifier"])

        return WebhookEventRawResults(
            updated_raw_results=[data_to_update], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields for an issue event."""
        return (
            isinstance(payload, dict)
            and "type" in payload
            and payload["type"] == "Issue"
            and "data" in payload
            and "identifier" in payload["data"]
        )
