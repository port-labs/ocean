from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)

from azure_integration.foundry.clients.webhook_client import iter_signing_secrets
from azure_integration.foundry.helpers.webhook_verification import (
    WebhookSignatureError,
    verify_standard_webhook,
)

WEBHOOK_PATH = "/webhook"


class AbstractFoundryWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        secrets = iter_signing_secrets()
        # Azure returns signing_secret only at webhook create; callers cannot set one.
        # When this process has no cached secret, accept and complete the run anyway.
        if not secrets:
            logger.warning(
                "Accepting Foundry webhook without signature verification "
                "(no cached signing secret in this process)"
            )
            return True

        request = self.event._original_request
        if request is None:
            logger.error("Cannot verify webhook signature without the original request")
            return False

        raw_body = await request.body()
        for secret in secrets:
            try:
                verify_standard_webhook(raw_body, headers, secret=secret)
                return True
            except WebhookSignatureError:
                continue

        logger.error(
            "Foundry webhook signature verification failed for all cached secrets"
        )
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload.get("type"), str) and bool(payload.get("id"))

    @staticmethod
    def get_event_type(payload: EventPayload) -> str:
        event_type = payload.get("type")
        return str(event_type) if event_type else ""
