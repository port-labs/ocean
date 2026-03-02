import json
import hmac
import hashlib
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from webhook_processors.events import ISSUE_EVENT_ACTIONS


class _SentryBaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for Sentry webhook processors with signature verification."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request."""
        expected_digest = headers.get("sentry-hook-signature")
        if not expected_digest:
            return False

        webhook_secret: str | None = ocean.integration_config.get(
            "sentry_webhook_secret"
        )
        if not webhook_secret:
            return False

        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        digest = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(digest, expected_digest)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        issue_id = payload.get("data", {}).get("issue", {}).get("id")
        action = payload.get("action")
        return issue_id is not None and action is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("sentry-hook-signature") is not None
            and event.payload.get("action") in ISSUE_EVENT_ACTIONS
            and event.headers.get("sentry-hook-resource") == "issue"
        )
