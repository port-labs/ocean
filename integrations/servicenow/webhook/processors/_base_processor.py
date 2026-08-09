from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventHeaders,
    EventPayload,
)
from abc import abstractmethod

from webhook.webhook_client import AUTHORIZATION_HEADER_NAME, WEBHOOK_SECRET_CONFIG_KEY


class ServicenowAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Base class for all ServiceNow webhook processors."""

    @abstractmethod
    def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        webhook_secret = ocean.integration_config.get(WEBHOOK_SECRET_CONFIG_KEY)
        if not webhook_secret:
            return True

        incoming_token = headers.get(AUTHORIZATION_HEADER_NAME.lower())
        if not incoming_token:
            logger.warning("Webhook request rejected — missing Authorization header")
            return False

        if incoming_token != webhook_secret:
            logger.warning("Webhook request rejected — Authorization header mismatch")
            return False

        logger.debug("Webhook request authenticated successfully")
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and self._should_process_event(event)):
            return False
        return "x-snc-integration-source" in event.headers

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "sys_id" in payload
