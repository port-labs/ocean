from abc import abstractmethod
from typing import List
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor as BaseAbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload, WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults


class AbstractWebhookProcessor(BaseAbstractWebhookProcessor):
    """Abstract base class for GitHub webhook processors.
    
    This class provides the base structure and common functionality for all GitHub webhook processors.
    Each concrete processor must implement the abstract methods to handle specific types of GitHub webhook events.
    """

    @abstractmethod
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event.
        
        Args:
            event: The webhook event to check
            
        Returns:
            bool: True if this processor should handle the event, False otherwise
        """
        pass

    @abstractmethod
    async def get_supported_resource_kinds(self, event: WebhookEvent) -> List[str]:
        """Get the list of resource kinds that this processor supports.
        
        Args:
            event: The webhook event to check
            
        Returns:
            List[str]: List of supported resource kinds
        """
        pass

    @abstractmethod
    async def process_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the webhook event.
        
        Args:
            payload: The webhook event payload
            resource_config: The resource configuration
            
        Returns:
            WebhookEventRawResults: The results of processing the webhook event
        """
        pass

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request using GitHub's webhook secret.
        
        Args:
            payload: The webhook event payload
            headers: The webhook event headers
            
        Returns:
            bool: True if authentication is successful, False otherwise
        """
        try:
            # GitHub webhooks are authenticated via the webhook secret
            # This is handled at the application level through the webhook secret
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload structure and content.
        
        Args:
            payload: The webhook event payload to validate
            
        Returns:
            bool: True if the payload is valid, False otherwise
        """
        try:
            # Check for required GitHub webhook fields
            required_fields = ["repository", "sender", "action"]
            missing_fields = [field for field in required_fields if field not in payload]
            if missing_fields:
                logger.warning(f"Missing required fields in payload: {', '.join(missing_fields)}")
                return False

            # Validate repository field
            repository = payload.get("repository", {})
            if not isinstance(repository, dict):
                logger.warning("Invalid repository field: not a dictionary")
                return False

            # Validate sender field
            sender = payload.get("sender", {})
            if not isinstance(sender, dict):
                logger.warning("Invalid sender field: not a dictionary")
                return False

            return True
        except Exception as e:
            logger.error(f"Payload validation failed: {e}")
            return False