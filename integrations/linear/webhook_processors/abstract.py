from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload


class LinearAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Linear webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Linear doesn't provide webhook authentication by default.
        Authentication is handled through the webhook URL which contains a secret.
        """
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
