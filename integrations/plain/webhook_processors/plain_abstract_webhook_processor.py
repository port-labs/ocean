from __future__ import annotations

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

from plain.webhook_signature import verify_plain_signature
from webhook_processors.utils import event_type


class PlainAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Shared Plain webhook auth and per-processor event gating."""

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Return True when this processor should handle the Plain event type."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload, dict) and bool(event_type(payload))

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not event._original_request:
            logger.error("Plain webhook event is missing the original request body")
            return False
        if not await self._should_process_event(event):
            return False

        secret = ocean.integration_config.get("webhook_secret")
        secret_value = str(secret) if secret else None
        body = await event._original_request.body()
        return verify_plain_signature(body, event.headers, secret_value)
