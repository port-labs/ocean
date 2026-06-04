from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload

from datadog.webhook.webhook_client import PORT_AUTH_HEADER_NAME


class BaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        webhook_secret = ocean.integration_config.get("webhook_secret")
        auth_header_value = self._get_auth_header_value(headers)

        if not webhook_secret:
            if auth_header_value:
                logger.warning(
                    f"{PORT_AUTH_HEADER_NAME} header present but no webhook "
                    "secret configured. "
                    "Configure webhook_secret to enable authentication."
                )
            else:
                logger.info("No webhook secret configured. Authentication disabled.")
            return not auth_header_value

        if not auth_header_value:
            logger.warning(
                f"Webhook authentication failed: missing "
                f"{PORT_AUTH_HEADER_NAME} header"
            )
            return False

        is_valid = auth_header_value == webhook_secret
        if not is_valid:
            logger.warning("Webhook authentication failed: invalid secret")
        return is_valid

    @staticmethod
    def _get_auth_header_value(headers: dict[str, Any]) -> str | None:
        expected_header_name = PORT_AUTH_HEADER_NAME.lower()
        for header_name, value in headers.items():
            if header_name.lower() == expected_header_name:
                return str(value)
        return None
