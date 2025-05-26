from abc import abstractmethod
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload
import hashlib
import hmac
from fastapi import Request
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)


class _GithubAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for GitHub webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """Verify that the payload was sent from GitHub by validating SHA256."""

        secret = ocean.integration_config["webhook_secret"]

        if not secret:
            logger.warning(
                "Skipping webhook signature verification because no secret is configured."
            )
            return True

        signature = request.headers.get("x-hub-signature-256")
        if not signature:
            logger.error(
                "Missing 'x-hub-signature-256' header. Webhook authentication failed."
            )
            return False

        payload = await request.body()
        hash_object = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
        computed_signature = "sha256=" + hash_object.hexdigest()

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
