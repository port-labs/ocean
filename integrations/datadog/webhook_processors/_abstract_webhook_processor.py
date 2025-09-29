import base64
import binascii
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
        authorization = headers.get("authorization")

        if not webhook_secret:
            if authorization:
                logger.warning(
                    "Authorization header present but no webhook secret configured. "
                    "Configure webhook_secret to enable authentication."
                )
            else:
                logger.info("No webhook secret configured. Authentication disabled.")
            return not authorization  # Allow only if no auth header is present

        if not authorization:
            logger.warning(
                "Webhook authentication failed: missing Authorization header"
            )
            return False

        return self._validate_basic_auth(authorization, webhook_secret)

    @staticmethod
    def _validate_basic_auth(authorization: str, expected_secret: str) -> bool:
        """Validate Basic Authentication header against expected webhook secret."""
        try:
            auth_parts = authorization.split(" ", 1)
            if len(auth_parts) != 2:
                logger.warning("Invalid authorization header format")
                return False

            auth_type, encoded_token = auth_parts
            if auth_type.lower() != "basic":
                logger.warning(f"Unsupported authorization type: {auth_type}")
                return False

            decoded_credentials = base64.b64decode(encoded_token).decode("utf-8")
            credential_parts = decoded_credentials.split(":", 1)
            if len(credential_parts) != 2:
                logger.warning("Invalid Basic Auth credentials format")
                return False

            _, provided_secret = credential_parts
            is_valid = provided_secret == expected_secret

            if not is_valid:
                logger.warning("Webhook authentication failed: invalid secret")

            return is_valid

        except (ValueError, UnicodeDecodeError, binascii.Error) as e:
            logger.warning(f"Error decoding authorization header: {str(e)}")
            return False
