"""Base webhook processor for Okta integration."""

import hashlib
import hmac
from abc import abstractmethod
from typing import Any, Dict

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.context.ocean import ocean

from okta.clients.client_factory import create_okta_client


class OktaBaseWebhookProcessor(AbstractWebhookProcessor):
    """Base webhook processor for Okta events."""

    def __init__(self):
        """Initialize the base webhook processor."""
        self.client = create_okta_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request.
        
        Okta event hooks don't use HMAC signatures like GitHub/Bitbucket.
        Instead, they use verification tokens or custom headers.
        For now, we'll accept all requests but this can be enhanced.
        
        Args:
            payload: The webhook payload
            headers: The request headers
            
        Returns:
            True if authenticated, False otherwise
        """
        # Okta event hooks can be configured with custom headers for authentication
        # For now, we'll accept all requests but this should be enhanced based on
        # the specific Okta event hook configuration
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload.
        
        Args:
            payload: The webhook payload
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation - check for required Okta event structure
        return (
            "eventType" in payload and
            "published" in payload and
            "eventId" in payload
        )

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event.
        
        Args:
            event: The webhook event
            
        Returns:
            True if should process, False otherwise
        """
        pass

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this processor should handle the event.
        
        Args:
            event: The webhook event
            
        Returns:
            True if should process, False otherwise
        """
        if not event._original_request:
            return False
        
        return await self._should_process_event(event)

    @abstractmethod
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get the resource kinds that this event affects.
        
        Args:
            event: The webhook event
            
        Returns:
            List of resource kinds
        """
        pass

    @abstractmethod
    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the webhook event.
        
        Args:
            payload: The webhook payload
            resource_config: The resource configuration
            
        Returns:
            Webhook event results
        """
        pass

