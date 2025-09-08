import base64
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


class _CheckmarxOneAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Checkmarx One webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """
        Validate the authenticity of the webhook payload using HMAC and the webhook secret.
        If no secret is configured, validation is bypassed.
        """

        secret = ocean.integration_config.get("webhook_secret")

        if not secret:
            logger.warning(
                "Skipping webhook signature verification because no secret is configured."
            )
            return True

        signature = request.headers.get("x-cx-webhook-signature")
        if not signature:
            logger.error(
                "Missing 'x-cx-webhook-signature' header. Webhook authentication failed."
            )
            return False

        payload = await request.body()
        hash_object = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)

        parsed_signature = signature.removeprefix("sha256=")
        expected_signature_hex = hash_object.hexdigest()
        expected_signature_b64 = base64.b64encode(hash_object.digest()).decode("utf-8")

        signature_valid = self._validate_signature_format(
            parsed_signature, expected_signature_hex, expected_signature_b64
        )

        logger.debug(
            "Validating webhook signature... signature present: %s, signature valid: %s",
            bool(signature),
            signature_valid,
        )

        return signature_valid

    def _validate_signature_format(
        self,
        parsed_signature: str,
        expected_signature_hex: str,
        expected_signature_b64: str,
    ) -> bool:
        """
        Validate signature by trying both hex and base64 comparison formats.
        Checkmarx might use either format for webhook signatures.
        """
        return hmac.compare_digest(
            parsed_signature, expected_signature_hex
        ) or hmac.compare_digest(parsed_signature, expected_signature_b64)

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and await self._should_process_event(event)):
            return False
        return await self._verify_webhook_signature(event._original_request)
