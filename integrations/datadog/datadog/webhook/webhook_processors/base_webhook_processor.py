from typing import Any, Awaitable, Callable, TypeVar

from httpx import HTTPStatusError
from loguru import logger
from datadog.client import DatadogClient
from client_manager import get_client_manager
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from datadog.webhook.webhook_client import PORT_AUTH_HEADER_NAME

T = TypeVar("T")


class BaseWebhookProcessor(AbstractWebhookProcessor):

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self._client_manager = get_client_manager()

    async def _fetch_from_clients(
        self,
        clients: list[DatadogClient],
        fetch: Callable[[DatadogClient], Awaitable[T]],
        *,
        context: str,
    ) -> T | None:
        """Run *fetch* against each candidate client, returning the first non-empty
        result.

        An org can map to several clients (shared names, or several key pairs for
        one org), and the event truly originates from whichever one can fetch its
        resource. A client whose credentials don't own the resource raises an HTTP
        error (403/404) — we log and try the next. Returns None when none yield data.
        """
        if not clients:
            logger.warning(f"No Datadog client configured for {context}; skipping event")
            return None

        for client in clients:
            try:
                result = await fetch(client)
            except HTTPStatusError as e:
                logger.warning(
                    f"Candidate client for {context} could not fetch the event's "
                    f"resource ({e.response.status_code}); trying next"
                )
                continue
            if result:
                return result

        logger.warning(f"No configured Datadog client returned data for {context}")
        return None

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
