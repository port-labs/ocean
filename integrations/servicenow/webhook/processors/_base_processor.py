from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    EventHeaders,
    EventPayload,
)
from abc import abstractmethod


class _ServicenowAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Base class for all ServiceNow webhook processors."""

    @abstractmethod
    def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """No authentication required"""
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and self._should_process_event(event)):
            return False
        return "x-snc-integration-source" in event.headers

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "sys_id" in payload
