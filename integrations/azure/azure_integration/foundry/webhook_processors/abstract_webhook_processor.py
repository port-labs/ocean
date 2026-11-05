from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from azure_integration.foundry.clients.webhook_client import (
    _signing_secrets,
)
from azure_integration.foundry.helpers.webhook_verification import (
    WebhookSignatureError,
    verify_standard_webhook,
)


class AbstractFoundryWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        if not _signing_secrets:
            logger.warning(
                "Skipping Foundry webhook verification because no in-process "
                "signing secret is available"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify webhook signature without the original request")
            return False

        raw_body = await request.body()
        for secret in _signing_secrets.values():
            try:
                verify_standard_webhook(raw_body, headers, secret=secret)
                return True
            except WebhookSignatureError:
                continue

        logger.error("Foundry webhook signature verification failed for all cached secrets")
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload.get("type"), str) and bool(payload.get("id"))

    @staticmethod
    def get_event_type(payload: EventPayload) -> str:
        event_type = payload.get("type")
        return str(event_type) if event_type else ""
