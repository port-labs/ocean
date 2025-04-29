from webhook_processors.linear_abstract_webhook_processor import (
    _LinearAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from linear.client import LinearClient
from linear.utils import ObjectKind
from loguru import logger


class IssueWebhookProcessor(_LinearAbstractWebhookProcessor):
    """Processes issue-related webhook events from Linear."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event header contains required Issue event type."""

        return event.headers.get(
            "linear-event"
        ) == "Issue" and await self.is_action_allowed(event.payload.get("action", ""))

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the issue webhook event and return the raw results."""
        event_data = payload["data"]
        identifier = event_data["identifier"]
        action = payload["action"]

        logger.info(f"Processing webhook event for issue: {identifier}")

        if action == "remove":
            logger.info(
                f"Issue #{identifier} was deleted from {event_data["team"]["name"]}"
            )

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[event_data],
            )

        client = LinearClient.create_from_ocean_configuration()
        data_to_update = await client.get_single_issue(identifier)

        return WebhookEventRawResults(
            updated_raw_results=[data_to_update], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields for an issue event."""
        return (
            isinstance(payload, dict)
            and all(key in payload for key in ("type", "data", "action"))
            and payload["type"] == "Issue"
            and "identifier" in payload["data"]
        )
