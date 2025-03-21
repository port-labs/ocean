import hashlib
import hmac
from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)


class BaseSonarQubeWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # Process events related to projects
        if not ocean.integration_config.get("webhook_secret"):
            return "project" in event.payload
        signature = event.headers.get("X-Sonar-Webhook-HMAC-SHA256", "")
        body = await event._original_request.body()
        computed_signature = hmac.new(
            ocean.integration_config["webhook_secret"].encode("utf-8"),
            str(body).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        process_event = "project" in event.payload and hmac.compare_digest(signature, computed_signature)
        return process_event

    async def authenticate(self, payload: EventPayload, headers: dict[str, Any]) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "project" in payload