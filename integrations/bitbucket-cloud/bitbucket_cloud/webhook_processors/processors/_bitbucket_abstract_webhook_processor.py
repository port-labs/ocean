from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from initialize_client import init_webhook_client
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from abc import abstractmethod

import hashlib
import hmac

from fastapi import Request
from loguru import logger


class _BitbucketAbstractWebhookProcessor(AbstractWebhookProcessor):

    _webhook_client = init_webhook_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """Authenticate the Bitbucket webhook payload using the secret.
        Skip if secret was not provided
        """
        if not self._webhook_client.secret:
            logger.warning(
                "No secret provided for authenticating incoming webhooks, skipping authentication."
            )
            return True

        signature = request.headers.get("x-hub-signature")

        if not signature:
            logger.error(
                "Aborting webhook authentication due to missing X-Hub-Signature header"
            )
            return False

        body = await request.body()

        hash_object = hmac.new(
            self._webhook_client.secret.encode(), body, hashlib.sha256
        )
        expected_signature = "sha256=" + hash_object.hexdigest()

        logger.debug(
            "Webhook authentication: Comparing signatures",
            received=signature,
            expected=expected_signature,
        )

        return hmac.compare_digest(signature, expected_signature)

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and await self._should_process_event(event)):
            return False
        return await self._verify_webhook_signature(event._original_request)
