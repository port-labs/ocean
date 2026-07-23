from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from core.webhook_signing import (
    derive_webhook_secret,
    get_webhook_signing_secret,
    verify_hmac_signature,
)
from webhook_processors.utils import extract_port_run_id_from_request

SIGNATURE_HEADER = "x-webhook-signature"


class AbstractCursorWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for Cursor Cloud Agents v0 status callbacks.

    When `webhookSigningSecret` is configured, Cursor's `X-Webhook-Signature`
    header is verified using a per-run secret derived from that installation
    secret, the org id, and the Port run id embedded in the callback URL path
    (see `core.webhook_signing`). When it is not configured, signature
    verification is skipped.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        if get_webhook_signing_secret() is None:
            logger.warning(
                "Skipping webhook signature verification because "
                "webhookSigningSecret is not configured"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify webhook signature without the original request")
            return False

        run_id = extract_port_run_id_from_request(request)
        if not run_id:
            logger.error(
                "Cursor webhook callback URL is missing the run_id path segment"
            )
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
        secret = await derive_webhook_secret(run_id)
        if secret is None:
            return True
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
