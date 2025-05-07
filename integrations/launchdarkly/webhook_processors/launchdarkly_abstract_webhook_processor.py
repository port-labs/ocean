from abc import abstractmethod
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from loguru import logger
import hashlib
import hmac

from fastapi import Request
from port_ocean.context.ocean import ocean


class _LaunchDarklyAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for LaunchDarkly webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """
        Validate the authenticity of the webhook payload using HMAC and the webhook secret.
        If no secret is configured, validation is bypassed.
        """

        secret = ocean.integration_config["webhook_secret"]

        if not secret:
            logger.warning(
                "Skipping webhook signature verification because no secret is configured."
            )
            return True

        signature = request.headers.get("x-ld-signature")
        if not signature:
            logger.error(
                "Missing 'x-ld-signature' header. Webhook authentication failed."
            )
            return False

        payload = await request.body()
        computed_signature = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        logger.debug(
            "Validating webhook signature...",
            extra={
                "received_signature": signature,
                "computed_signature": computed_signature,
            },
        )

        return hmac.compare_digest(signature, computed_signature)

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and await self._should_process_event(event)):
            return False
        return await self._verify_webhook_signature(event._original_request)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains all required fields."""
        return not ({"kind", "_links", "accesses"} - payload.keys())

    def is_deletion_event(self, payload: EventPayload) -> bool:
        """
        Returns True if the event is a deletion or archive event based on the payload's titleVerb.
        """
        return any(word in payload["titleVerb"] for word in ["deleted", "archived"])
