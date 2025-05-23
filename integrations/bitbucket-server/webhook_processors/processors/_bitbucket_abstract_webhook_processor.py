from abc import abstractmethod
from typing import Any

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook_processors.webhook_client import initialize_client


class BaseWebhookProcessorMixin(AbstractWebhookProcessor):
    _client = initialize_client()

    async def authenticate(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> bool:
        return True

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and await self._should_process_event(event)):
            return False

        return await self._client.verify_webhook_signature(event._original_request)

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        return True
