import base64
import hmac
from typing import Any
from loguru import logger
from client import OctopusClient
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)
from init_client import init_octopus_client


class BaseOctopusWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        webhook_id = headers.get("x-octopus-webhook-id")
        webhook_secret = ocean.integration_config.get("webhook_secret", "")

        if webhook_id:
            try:
                decoded_id = base64.b64decode(webhook_id).decode("utf-8")
                return hmac.compare_digest(decoded_id, webhook_secret)
            except (ValueError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to decode webhook ID: {e}")
                return False
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "Payload" in payload and "Event" in payload.get("Payload", {})

    async def get_client(self) -> OctopusClient:
        """Initialize a new client instance when needed"""
        return init_octopus_client()
