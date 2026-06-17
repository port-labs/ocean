from typing import Any

from loguru import logger
from datadog.client import DatadogClient
from initialize_client import get_client_manager
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from datadog.webhook.webhook_client import (
    PORT_AUTH_HEADER_NAME,
    PORT_DATADOG_ORG_HEADER_NAME,
)


class BaseWebhookProcessor(AbstractWebhookProcessor):

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self._client_manager = get_client_manager()

    def _get_client_for_org_uuid(
        self, org_uuid: str | None
    ) -> DatadogClient | None:
        """Select the Datadog client responsible for the org with *org_uuid*.

        Delegates to the client manager: single-org installs always use their sole
        client; multi-org installs match the org uuid (the credential-map key)
        against the configured orgs, returning None (so callers skip the event)
        when nothing matches. The uuid is exposed differently per event family
        (monitor webhooks carry it in a stamped header, audit-trail events in the
        payload), so each family extracts it and calls here.
        """
        return self._client_manager.get_client_by_org_uuid(org_uuid)

    def _org_uuid_from_event_headers(self) -> str | None:
        """Read the org uuid we stamp onto each org's monitor webhook at creation."""
        return self._get_header_value(self.event.headers, PORT_DATADOG_ORG_HEADER_NAME)

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

    def _get_auth_header_value(self, headers: dict[str, Any]) -> str | None:
        return self._get_header_value(headers, PORT_AUTH_HEADER_NAME)

    @staticmethod
    def _get_header_value(headers: dict[str, Any], name: str) -> str | None:
        expected_header_name = name.lower()
        for header_name, value in headers.items():
            if header_name.lower() == expected_header_name:
                return str(value)
        return None

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
