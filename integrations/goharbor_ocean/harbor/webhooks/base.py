"""Abstract base class for Harbor webhook processors."""

from abc import abstractmethod

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)

EventHeaders = dict[str, str]


class HarborAbstractBaseWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Harbor webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request using Authorization header."""
        secret = ocean.integration_config.get("webhook_secret")

        if not secret:
            logger.warning("Skipping webhook signature verification because no secret is configured.")
            return True

        received_token = headers.get("authorization") or headers.get("Authorization")
        if not received_token:
            logger.error("Missing 'Authorization' header. Harbor webhook authentication failed.")
            return False

        return received_token == secret

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this event should be processed. Always return True since authentication is handled in authenticate method."""
        return True

    @abstractmethod
    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validates incoming payload against Harbor specifications."""
