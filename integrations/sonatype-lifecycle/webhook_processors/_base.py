import hashlib
import hmac

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

# IQ sets these headers on every webhook delivery.
WEBHOOK_ID_HEADER = "x-nexus-webhook-id"
WEBHOOK_SIGNATURE_HEADER = "x-nexus-webhook-signature"

# X-Nexus-Webhook-Id values (event types) we care about.
APPLICATION_EVALUATION_EVENT = "iq:applicationEvaluation"
POLICY_MANAGEMENT_EVENT = "iq:policyManagement"


class SonatypeAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Common auth + validation for all Sonatype webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Verify the request came from the configured IQ Server.

        Sonatype signs the *raw* request body with HMAC-SHA1 using the secret
        key configured alongside the webhook, and sends it as a hex digest in
        the ``X-Nexus-Webhook-Signature`` header. If a ``webhookSecret`` is
        configured we verify it strictly; if not, we accept deliveries that at
        least carry a Nexus webhook id header.
        """
        if WEBHOOK_ID_HEADER not in headers:
            logger.warning("Rejecting webhook with no Nexus webhook id header")
            return False

        secret = ocean.integration_config.get("webhook_secret")
        if not secret:
            return True

        signature = headers.get(WEBHOOK_SIGNATURE_HEADER)
        if not signature:
            logger.warning("Webhook secret is set but request carried no signature")
            return False

        raw_body = await self._raw_body()
        if raw_body is None:
            logger.error(
                "Cannot verify webhook signature: raw request body unavailable"
            )
            return False

        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha1).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning("Webhook signature verification failed")
            return False
        return True

    async def _raw_body(self) -> bytes | None:
        original_request = getattr(self.event, "_original_request", None)
        if original_request is None:
            return None
        return await original_request.body()

    async def should_process_event(self, event: WebhookEvent) -> bool:
        raise NotImplementedError

    @staticmethod
    def _event_id(event: WebhookEvent) -> str:
        return event.headers.get(WEBHOOK_ID_HEADER, "")
