from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from core.webhook_signing import derive_webhook_secret, verify_hmac_signature
from webhook_processors.utils import extract_port_run_id_from_request

SIGNATURE_HEADER = "x-webhook-signature"


class AbstractCursorWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for Cursor Cloud Agents v0 status callbacks.

    Cursor signs the raw JSON body with HMAC-SHA256 using the webhook secret
    configured at agent-launch time, sent as `X-Webhook-Signature: sha256=<hex>`.
    The secret needs no customer configuration - it's derived from the Port
    run id embedded in the callback URL path (see `core.webhook_signing`),
    so verification is always enforced, never skipped.
    """

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
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
        return verify_hmac_signature(secret, raw_body, signature)

    async def validate_payload(self, payload: EventPayload) -> bool:
        return bool(payload.get("id") and payload.get("status"))
