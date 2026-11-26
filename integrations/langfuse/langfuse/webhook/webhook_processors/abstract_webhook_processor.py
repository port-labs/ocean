from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from langfuse.webhook.signature import (
    SIGNATURE_HEADER,
    get_webhook_secret,
    verify_langfuse_signature,
)


class AbstractLangfuseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        secret = get_webhook_secret()
        if secret is None:
            logger.warning(
                "Skipping Langfuse webhook signature verification "
                "(webhookSecret not configured)"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify Langfuse webhook without original request body")
            return False

        signature = next(
            (v for k, v in headers.items() if k.lower() == SIGNATURE_HEADER),
            None,
        )
        if not signature:
            logger.error("Langfuse webhook missing x-langfuse-signature header")
            return False

        raw_body = (await request.body()).decode("utf-8")
        return verify_langfuse_signature(raw_body, signature, secret)
