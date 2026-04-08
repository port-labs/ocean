import hmac
import hashlib

from fastapi import Request
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
from webhook_processors.events import ISSUE_EVENT_ACTIONS


class _SentryBaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for Sentry webhook processors with signature verification."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """Verify that the payload was sent from Sentry by validating HMAC-SHA256."""
        webhook_secret: str | None = ocean.integration_config.get(
            "sentry_webhook_secret"
        )
        signature = request.headers.get("sentry-hook-signature")

        if not webhook_secret:
            logger.debug(
                "Skipping webhook signature verification because no secret is configured"
            )
            return True

        if not signature:
            logger.error(
                "Webhook secret is configured but the incoming event is missing "
                "the 'sentry-hook-signature' header. Rejecting event."
            )
            return False

        body = await request.body()
        digest = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(digest, signature)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the integration webhook payload."""
        issue_id = payload.get("data", {}).get("issue", {}).get("id")
        action = payload.get("action")
        return issue_id is not None and action is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (
            event._original_request
            and event.payload.get("action") in ISSUE_EVENT_ACTIONS
            and event.headers.get("sentry-hook-resource") == "issue"
        ):
            return False

        return await self._verify_webhook_signature(event._original_request)
