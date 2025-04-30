from webhook_processors.utils import WebhookAction
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class _LinearAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Linear webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def is_action_allowed(self, action: str) -> bool:
        try:
            return WebhookAction(action) in WebhookAction
        except ValueError:
            return False
