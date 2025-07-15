import base64
from loguru import logger
from typing import Any

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload


class _AbstractDatadogWebhookProcessor(AbstractWebhookProcessor):

    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        webhook_secret = ocean.integration_config.get("webhook_secret")
        if not webhook_secret:
            logger.info("No webhook secret found. Skipping authentication")
            return True

        authorization = headers.get("authorization")
        if not authorization:
            logger.warning(
                "Webhook authentication failed due to missing Authorization header in the event"
            )
            return False

        try:
            auth_type, encoded_token = authorization.split(" ", 1)
            if auth_type.lower() != "basic":
                logger.warning(f"Invalid authorization type: {auth_type}")
                return False

            decoded = base64.b64decode(encoded_token).decode("utf-8")
            _, token = decoded.split(":", 1)
            is_valid = token == webhook_secret

            if not is_valid:
                logger.warning("Invalid webhook secret")

            return is_valid
        except (ValueError, UnicodeDecodeError) as e:
            logger.warning(f"Error decoding authorization header: {str(e)}")
            return False
