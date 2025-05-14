from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)
from loguru import logger


class _JenkinsAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Jenkins webhook processors."""

    def __init__(self, event: WebhookEvent) -> None:
        if (
            event._original_request
            and "integration/events" in event._original_request.url.path
        ):
            logger.warning(
                "'integration/events' webhook endpoint path is deprecated. Please use 'integration/webhook' instead."
            )

        super().__init__(event)

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Jenkins authentication is handled through basic auth in the client.
        """
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains all required fields."""
        return not ({"type", "url", "data", "source"} - payload.keys())
