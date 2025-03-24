from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from initialize_client import init_webhook_client
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from abc import abstractmethod


class _BitbucketAbstractWebhookProcessor(AbstractWebhookProcessor):

    _webhook_client = init_webhook_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and await self._should_process_event(event)):
            return False
        return await self._webhook_client.authenticate_incoming_webhook(
            event._original_request
        )
