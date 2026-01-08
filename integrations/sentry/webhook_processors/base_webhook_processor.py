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

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        ...

    @abstractmethod
    def _validate_integration_payload(self, payload: EventPayload) -> bool:
        """Validate the custom integration webhook payload."""
        ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not event._original_request:
            return False
        if not await self._should_process_event(event):
            return False
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        # todo - separate logic for custom integration and service hook
        if "group" in payload and "project" in payload:
            return True

        return self._validate_integration_payload(payload)
