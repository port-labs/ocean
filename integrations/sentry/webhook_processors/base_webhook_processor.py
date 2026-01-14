from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from webhook_processors.events import EVENT_ACTIONS


class _SentryBaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for Sentry webhook processors with signature verification."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request."""
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        issue_id = payload.get("data", {}).get("issue", {}).get("id")
        action = payload.get("action")
        return issue_id is not None and action is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("sentry-hook-signature") is not None
            and event.payload.get("action") in EVENT_ACTIONS
            and event.headers.get("sentry-hook-resource") == "issue"
        )
