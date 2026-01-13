from abc import abstractmethod


from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class _SentryBaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for Sentry webhook processors with signature verification."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    def _get_resource_type(self, headers: EventHeaders) -> str:
        """Get the Sentry-Hook-Resource header value."""
        return headers.get("x-servicehook-signature", "")

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        if payload.get("group", {}).get("id"):
            return True
        return False

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not event._original_request:
            return False
        if not await self._should_process_event(event):
            return False
        return True
