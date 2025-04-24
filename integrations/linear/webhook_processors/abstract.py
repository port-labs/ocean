from abc import abstractmethod
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class LinearAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Linear webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Validate webhook event has required structure and passes processor-specific checks."""

        if not event._original_request:
            return False

        return await self._should_process_event(event)
