from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload

from aws.webhook.consts import LIVE_EVENTS_API_KEY_HEADER


class BaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: EventPayload, headers: dict[str, Any]
    ) -> bool:
        expected_api_key = ocean.integration_config.get("live_events_api_key")
        if not expected_api_key:
            logger.warning(
                "liveEventsApiKey is not configured; rejecting all live events"
            )
            return False

        provided_api_key = self._get_auth_header_value(headers)
        return provided_api_key == expected_api_key

    @staticmethod
    def _get_auth_header_value(headers: dict[str, Any]) -> str | None:
        expected_header_name = LIVE_EVENTS_API_KEY_HEADER.lower()
        for header_name, value in headers.items():
            if header_name.lower() == expected_header_name:
                return str(value)
        return None
