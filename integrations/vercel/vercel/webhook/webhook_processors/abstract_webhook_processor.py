"""Abstract base class for Vercel webhook processors."""

from abc import ABC, abstractmethod

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class AbstractVercelWebhookProcessor(ABC):
    """Abstract base class for processing Vercel webhook events."""

    @abstractmethod
    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required fields."""
        ...

    @abstractmethod
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the resource kinds affected by this event."""
        ...

    @abstractmethod
    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the webhook event and return raw results."""
        ...

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        return True
