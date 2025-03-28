import hashlib
import hmac
from typing import Any
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)
from loguru import logger


class BaseSonarQubeWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if webhook event should be processed based on signature and payload"""
        if event._original_request is None:
            return False

        webhook_secret = ocean.integration_config.get("webhook_secret")
        signature = event.headers.get("x-sonar-webhook-hmac-sha256", "")

        # If signature provided but no webhook secret configured
        if signature and not webhook_secret:
            logger.warning(
                "Signature found but no secret configured for authenticating incoming webhooks, skipping event."
            )
            return False

        # If no webhook secret configured, process event without authentication
        if not webhook_secret:
            logger.info(
                "No secret provided for authenticating incoming webhooks, skipping webhook authentication."
            )
            return True

        # Verify signature if webhook secret configured
        body = await event._original_request.body()
        computed_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, computed_signature)

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "project" in payload
