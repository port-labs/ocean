from client import StatusPageClient
from initialize_client import init_client
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class BaseWebhookProcessor(AbstractWebhookProcessor):
    _client: StatusPageClient | None

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self._client = None

    @property
    def client(self) -> StatusPageClient:
        if self._client is None:
            self._client = init_client()
        return self._client

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
