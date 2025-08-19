from typing import Any, Dict, List, Optional

from loguru import logger
from port_ocean.context.event import event

from webhook_processors.base_webhook_processor import ZendeskBaseWebhookProcessor

"""
Organization webhook processor for Zendesk organization events

Based on Zendesk webhook event types documentation:
https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/

Purpose: Process real-time webhook events for Zendesk organizations  
Expected output: Processed organization data for Port synchronization
"""


class OrganizationWebhookProcessor(ZendeskBaseWebhookProcessor):
    """
    Webhook processor for Zendesk organization events
    
    Handles organization-related webhook events including:
    - Organization creation, updates, deletion
    - Domain changes
    - Settings modifications
    """
    
    def get_supported_events(self) -> List[str]:
        """
        Get list of supported organization event types
        
        Based on: https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/
        
        Returns:
            List of Zendesk organization event type strings
        """
        return [
            "zen:event-type:organization.created",
            "zen:event-type:organization.updated", 
            "zen:event-type:organization.deleted",
            "zen:event-type:organization.custom_field_changed",
            "zen:event-type:organization.domain_name_added",
            "zen:event-type:organization.domain_name_removed",
        ]
    
    async def should_process_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Determine if this webhook should be processed
        
        Purpose: Filter webhook events to only process supported organization events
        Expected output: Boolean indicating whether to process the webhook
        """
        if not self.validate_payload_structure(webhook_data):
            return False
        
        event_type = self.get_event_type(webhook_data)
        if not event_type or not self.is_supported_event(event_type):
            logger.debug(f"Unsupported organization event type: {event_type}")
            return False
        
        return True
    
    async def process_webhook(
        self, webhook_data: Dict[str, Any], raw_webhook_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Process Zendesk organization webhook event
        
        Purpose: Transform Zendesk webhook data into format suitable for Port sync
        Expected output: List containing the processed organization data
        """
        
        if not await self.should_process_webhook(webhook_data):
            return None
        
        event_type = self.get_event_type(webhook_data)
        detail = self.extract_detail_from_payload(webhook_data)
        event_data = self.extract_event_from_payload(webhook_data)
        
        if not detail:
            logger.warning(f"No detail data found in organization webhook: {event_type}")
            return None
        
        self.log_event_processing(event_type, detail)
        
        # For organization deletion events, we might want to handle differently
        if event_type == "zen:event-type:organization.deleted":
            logger.info(f"Processing organization deletion for ID: {detail.get('id')}")
            # Could implement deletion logic here if needed
        
        # For domain changes, log the change for visibility
        if "domain_name" in event_type and event_data:
            domain = event_data.get("domain_name")
            logger.info(f"Organization {detail.get('id')} domain event: {event_type} - {domain}")
        
        # Add event metadata to the organization data
        enriched_detail = detail.copy()
        enriched_detail["webhook_event_type"] = event_type
        enriched_detail["webhook_event_data"] = event_data
        
        # Return the organization data for synchronization
        return [enriched_detail]