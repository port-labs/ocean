import hashlib
import hmac
from abc import abstractmethod

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


class _SentryBaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for Sentry webhook processors with signature verification."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """
        Validate the authenticity of the webhook payload using HMAC-SHA256.

        Sentry sends a signature in the 'Sentry-Hook-Signature' header.
        The signature is computed as HMAC-SHA256(secret, body).
        If no secret is configured, validation is bypassed.
        """
        secret = ocean.integration_config.get("sentry_webhook_secret")

        if not secret:
            logger.info(
                "No secret configured for Sentry incoming webhooks; "
                "accepting event without signature validation."
            )
            return True

        signature = request.headers.get("sentry-hook-signature", "")
        if not signature:
            logger.error(
                "Missing 'Sentry-Hook-Signature' header. Webhook authentication failed."
            )
            return False

        # Get raw request body for signature verification
        body = await request.body()
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            logger.error("Sentry webhook signature verification failed.")
            return False

        return True

    def _get_resource_type(self, headers: EventHeaders) -> str:
        """Get the Sentry-Hook-Resource header value."""
        return headers.get("sentry-hook-resource", "")

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event."""
        ...

    @abstractmethod
    def _validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not event._original_request:
            return False
        if not await self._should_process_event(event):
            return False
        return await self._verify_webhook_signature(event._original_request)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        if not isinstance(payload, dict):
            return False

        if "action" not in payload:
            return False

        if "data" not in payload:
            return False

        if "installation" not in payload:
            return False

        return self._validate_payload(payload)
