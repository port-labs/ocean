from abc import abstractmethod
from typing import Any

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


class BaseJFrogWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for JFrog events"""

    async def authenticate(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> bool:
        """
        Authenticate webhook request.

        For now, we accept all requests. In production, you should:
        - Verify webhook secret/signature
        - Check source IP address
        - Validate request headers
        """
        return True

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event"""
        ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event"""
        return await self._should_process_event(event)

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        """Validate the webhook payload structure"""
        return True
