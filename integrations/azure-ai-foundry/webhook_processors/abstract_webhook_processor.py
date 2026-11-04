from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from clients.client_factory import create_webhook_client
from helpers.webhook_verification import WebhookSignatureError, verify_standard_webhook


class AbstractFoundryWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        client = create_webhook_client()
        if not client.verify_webhook_secrets:
            return True
        if not client.has_webhook_secret:
            logger.warning(
                "Skipping Foundry webhook verification because webhookSigningSecret "
                "is not configured"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify webhook signature without the original request")
            return False

        try:
            raw_body = await request.body()
            verify_standard_webhook(
                raw_body, headers, secret=client.signing_secret or ""
            )
            return True
        except WebhookSignatureError as error:
            logger.error(f"Foundry webhook signature verification failed: {error}")
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload.get("type"), str) and bool(payload.get("id"))

    @staticmethod
    def get_event_type(payload: EventPayload) -> str:
        event_type = payload.get("type")
        return str(event_type) if event_type else ""
