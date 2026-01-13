from port_ocean.context.ocean import ocean
from abc import abstractmethod
import json
import hmac
import hashlib

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
        """Authenticate the webhook request."""
        expected_digest = headers.get("sentry-hook-signature")
        if not expected_digest:
            # no authentication required for webhooks registered via API
            return True

        webhook_secret: str | None = ocean.integration_config.get(
            "sentry_webhook_secret"
        )
        if not webhook_secret:
            return False
        try:
            body = json.dumps(
                payload, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        except (TypeError, ValueError):
            return False

        digest = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(digest, expected_digest)

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
