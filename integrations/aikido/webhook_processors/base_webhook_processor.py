from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    EventHeaders,
    WebhookEvent,
)
from loguru import logger
from initialize_client import init_aikido_client
import hmac
import hashlib


class BaseAikidoWebhookProcessor(AbstractWebhookProcessor):
    _webhook_client = init_aikido_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, event: WebhookEvent) -> bool:
        webhook_secret = ocean.integration_config.get("webhook_secret")
        signature = event.headers.get("x-aikido-webhook-signature", "")

        if signature and not webhook_secret:
            logger.warning(
                "Signature found but no secret configured for authenticating incoming webhooks, skipping event."
            )
            return False

        if not webhook_secret:
            logger.info(
                "No secret provided for authenticating incoming webhooks, skipping webhook authentication."
            )
            return True

        if not event._original_request:
            return False

        body = await event._original_request.body()
        computed_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, computed_signature):
            logger.warning("Webhook signature verification failed")
            return False
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return await self._verify_webhook_signature(event)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload"""
        return (
            payload.get("event_type", "").startswith("issue")
            and payload.get("payload", {}).get("issue_id") is not None
        )
