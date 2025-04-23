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


class LabelWebhookProcessor(LinearAbstractWebhookProcessor):
    """Processes label-related webhook events from Linear."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the payload contains required fields and is a label event."""

        payload = event.payload
        return (
            isinstance(payload, dict)
            and "type" in payload
            and payload["type"] == "IssueLabel"
            and "data" in payload
            and "id" in payload["data"]
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.LABEL]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the label webhook event and return the raw results."""
        client = LinearClient.from_ocean_configuration()
        event_data = payload["data"]

        logger.info(
            f'Processing webhook event for label with ID: {event_data["id"]} and name: {event_data["name"]}'
        )
        data_to_update = await client.get_single_label(event_data["id"])

        return WebhookEventRawResults(
            updated_raw_results=[data_to_update], deleted_raw_results=[]
        )
