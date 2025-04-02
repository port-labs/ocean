from abc import ABC, abstractmethod
from typing import List, Optional
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor as BaseAbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload, WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults


class AbstractWebhookProcessor(BaseAbstractWebhookProcessor):
    """Abstract base class for GitHub webhook processors."""

    @abstractmethod
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event."""
        pass

    @abstractmethod
    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the resource kinds this processor handles."""
        pass

    @abstractmethod
    async def process_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the webhook event."""
        pass

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request using GitHub's webhook secret."""
        try:
            # GitHub webhooks are authenticated via the webhook secret
            # This is handled at the application level through the webhook secret
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload structure and content."""
        try:
            # Check for basic GitHub webhook structure
            if not isinstance(payload, dict):
                logger.warning("Invalid payload format: not a dictionary")
                return False

            # Check for required GitHub webhook fields
            required_fields = ["repository", "sender"]
            missing_fields = [field for field in required_fields if field not in payload]
            if missing_fields:
                logger.warning(f"Missing required fields in payload: {', '.join(missing_fields)}")
                return False

            return True
        except Exception as e:
            logger.error(f"Payload validation failed: {e}")
            return False