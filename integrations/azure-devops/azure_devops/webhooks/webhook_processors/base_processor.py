import base64
from typing import Dict
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class AzureDevOpsBaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: EventPayload, headers: Dict[str, str]
    ) -> bool:
        authorization = headers.get("authorization")
        webhook_secret = ocean.integration_config.get("webhook_secret")

        if authorization:
            try:
                auth_type, encoded_token = authorization.split(" ", 1)
                if auth_type.lower() != "basic":
                    return False

                decoded = base64.b64decode(encoded_token).decode("utf-8")
                _, token = decoded.split(":", 1)
                return token == webhook_secret
            except (ValueError, UnicodeDecodeError):
                return False
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Base payload validation"""
        required_fields = ["eventType", "publisherId", "resource"]
        return all(field in payload for field in required_fields)
