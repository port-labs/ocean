from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor as BaseAbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload


class AbstractWebhookProcessor(BaseAbstractWebhookProcessor):
    """Abstract base class for GitHub webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True