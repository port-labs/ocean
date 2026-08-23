from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from core.webhook_signing import get_webhook_signing_secret, verify_hmac_signature

SIGNATURE_HEADER = "x-webhook-signature"


class AbstractCursorWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for Cursor Cloud Agents v0 status callbacks.

    When `webhookSigningSecret` is configured, Cursor's `X-Webhook-Signature`
    header is verified with that secret. When it is not configured, signature
    verification is skipped.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        secret = get_webhook_signing_secret()
        if secret is None:
            logger.warning(
                "Skipping webhook signature verification because "
                "webhookSigningSecret is not configured"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify webhook signature without the original request")
            return False

        signature = next(
            (
                value
                for key, value in headers.items()
                if key.lower() == SIGNATURE_HEADER
            ),
            None,
        )
        if not signature:
            logger.error("Cursor webhook is missing the X-Webhook-Signature header")
            return False

        raw_body = (await request.body()).decode("utf-8")
        return verify_hmac_signature(secret, raw_body, signature)

    async def validate_payload(self, payload: EventPayload) -> bool:
        agent_id = payload.get("id")
        status = payload.get("status")
        return (
            isinstance(agent_id, str)
            and bool(agent_id)
            and isinstance(status, str)
            and bool(status)
        )
