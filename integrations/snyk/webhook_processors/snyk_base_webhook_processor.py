import hashlib
import hmac
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class SnykBaseWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        signature = event.headers.get("x-hub-signature", "")
        if event._original_request is None:
            return False
        body = await event._original_request.body()
        hmac_obj = hmac.new(
            ocean.integration_config["webhook_secret"].encode("utf-8"),
            body,
            hashlib.sha256,
        )
        expected_signature = f"sha256={hmac_obj.hexdigest()}"
        return signature == expected_signature

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "project" in payload
