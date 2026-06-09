from typing import Any

from loguru import logger
from datadog.client import DatadogClient
from initialize_client import get_client_manager
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from datadog.webhook.webhook_client import PORT_AUTH_HEADER_NAME


class BaseWebhookProcessor(AbstractWebhookProcessor):

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self._client_manager = get_client_manager()

    @staticmethod
    def _extract_org_id(payload: EventPayload) -> str | None:
        org_id = payload.get("org_id")
        return str(org_id) if org_id is not None else None

    def _get_client_for_payload(
        self, payload: EventPayload
    ) -> DatadogClient | None:
        """Select the Datadog client responsible for the org that emitted the event.

        Delegates to the client manager: single-org installs always use their sole
        client; multi-org installs match the payload's org id against the configured
        credential map, returning None (so callers skip the event) when nothing matches.
        """
        return self._client_manager.get_client_for_org(self._extract_org_id(payload))

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
                logger.debug("No webhook secret configured. Authentication disabled.")
            return True

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

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
