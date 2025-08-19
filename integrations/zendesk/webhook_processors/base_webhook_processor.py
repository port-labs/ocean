from abc import ABC
from typing import Any, Dict, List, Optional

from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)

"""
Base webhook processor for Zendesk events

Based on Zendesk webhook documentation:
- Webhook API: https://developer.zendesk.com/api-reference/webhooks/webhooks-api/webhooks/
- Event types: https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/
- Ticket events: https://developer.zendesk.com/api-reference/webhooks/event-types/ticket-events/

Purpose: Provide common functionality for all Zendesk webhook processors
Expected output: Base class with common webhook processing methods
"""


class ZendeskBaseWebhookProcessor(AbstractWebhookProcessor, ABC):
    """
    Abstract base class for Zendesk webhook processors
    
    Provides common functionality for processing Zendesk webhook events:
    - Event validation and parsing
    - Common payload extraction methods
    - Logging and error handling
    """
    
    def is_supported_event(self, event_type: str) -> bool:
        """
        Check if the event type is supported by this processor
        
        Args:
            event_type: The Zendesk event type (e.g., "zen:event-type:ticket.created")
            
        Returns:
            bool: True if the event type is supported
        """
        supported_events = self.get_supported_events()
        return event_type in supported_events
    
    def get_supported_events(self) -> List[str]:
        """
        Get list of supported event types for this processor
        
        Returns:
            List[str]: List of supported Zendesk event types
        """
        raise NotImplementedError("Subclasses must implement get_supported_events")
    
    def extract_detail_from_payload(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract the detail object from Zendesk webhook payload
        
        Based on Zendesk webhook payload structure:
        {
            "account_id": "...",
            "detail": { ... ticket/user/org data ... },
            "event": { ... event-specific data ... },
            "event_type": "zen:event-type:..."
        }
        
        Purpose: Extract the main object data from webhook payload
        Expected output: Detail object containing the main resource data
        """
        return webhook_data.get("detail")
    
    def extract_event_from_payload(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract the event object from Zendesk webhook payload
        
        Purpose: Extract event-specific data (e.g., status changes, field updates)
        Expected output: Event object containing change details
        """
        return webhook_data.get("event")
    
    def get_event_type(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract event type from webhook payload
        
        Purpose: Identify the type of Zendesk event
        Expected output: Event type string (e.g., "zen:event-type:ticket.created")
        """
        return webhook_data.get("event_type")
    
    def get_account_id(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract Zendesk account ID from webhook payload
        
        Purpose: Identify which Zendesk account generated the event
        Expected output: Account ID string
        """
        return webhook_data.get("account_id")
    
    def validate_payload_structure(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Validate that the webhook payload has the expected Zendesk structure
        
        Purpose: Ensure payload is a valid Zendesk webhook
        Expected output: Boolean indicating valid structure
        """
        required_fields = ["account_id", "event_type", "detail"]
        
        for field in required_fields:
            if field not in webhook_data:
                logger.warning(f"Missing required field '{field}' in webhook payload")
                return False
        
        return True
    
    def log_event_processing(self, event_type: str, detail: Dict[str, Any]) -> None:
        """
        Log webhook event processing for debugging
        
        Purpose: Provide consistent logging for webhook event processing
        Expected output: Structured log entry
        """
        resource_id = detail.get("id", "unknown")
        logger.info(f"Processing Zendesk webhook event: {event_type} for resource ID: {resource_id}")