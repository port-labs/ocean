from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class BaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for all GCP webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True
