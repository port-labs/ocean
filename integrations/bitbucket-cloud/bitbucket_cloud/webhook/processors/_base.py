from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from initialize_client import init_webhook_client
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload


class _BitbucketAbstractWebhookProcessor(AbstractWebhookProcessor):

    _webhook_client = init_webhook_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return await self._webhook_client.authenticate_incoming_webhook(
            payload, headers
        )
