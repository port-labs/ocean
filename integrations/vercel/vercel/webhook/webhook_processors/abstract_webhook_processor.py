"""Abstract base class for Vercel webhook processors."""

import hashlib
import hmac
from abc import abstractmethod

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class AbstractVercelWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for processing Vercel webhook events."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Validate the HMAC-SHA1 signature from Vercel when a secret is configured."""
        secret = ocean.integration_config.get("webhookSecret")
        if not secret:
            return True

        sig_header = headers.get("x-vercel-signature", "")
        if not sig_header:
            logger.warning("Missing x-vercel-signature header; rejecting webhook.")
            return False

        if self.event._original_request is None:
            return True

        raw_body = await self.event._original_request.body()
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha1).hexdigest()
        return hmac.compare_digest(expected, sig_header)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Delegate to subclass-specific event type check."""
        return await self._should_process_event(event)

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Return True if this processor handles the given event type."""
        ...
