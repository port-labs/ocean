from typing import Any, Dict, List, Optional

from loguru import logger
from port_ocean.context.event import event

from webhook_processors.base_webhook_processor import ZendeskBaseWebhookProcessor

"""
Ticket webhook processor for Zendesk ticket events

Based on Zendesk ticket events documentation:
https://developer.zendesk.com/api-reference/webhooks/event-types/ticket-events/

Purpose: Process real-time webhook events for Zendesk tickets
Expected output: Processed ticket data for Port synchronization
"""


class TicketWebhookProcessor(ZendeskBaseWebhookProcessor):
    """
    Webhook processor for Zendesk ticket events
    
    Handles all ticket-related webhook events including:
    - Ticket creation, updates, deletion
    - Status, priority, assignee changes
    - Comment additions
    - Custom field updates
    """
    
    def get_supported_events(self) -> List[str]:
        """
        Get list of supported ticket event types
        
        Based on: https://developer.zendesk.com/api-reference/webhooks/event-types/ticket-events/
        
        Returns:
            List of Zendesk ticket event type strings
        """
        return [
            "zen:event-type:ticket.created",
            "zen:event-type:ticket.updated", 
            "zen:event-type:ticket.status_changed",
            "zen:event-type:ticket.priority_changed",
            "zen:event-type:ticket.assignee_changed",
            "zen:event-type:ticket.group_changed",
            "zen:event-type:ticket.comment_added",
            "zen:event-type:ticket.comment_made_private",
            "zen:event-type:ticket.comment_made_public",
            "zen:event-type:ticket.tag_added",
            "zen:event-type:ticket.tag_removed",
            "zen:event-type:ticket.custom_field_changed",
            "zen:event-type:ticket.merged",
            "zen:event-type:ticket.deleted",
        ]
    
    async def should_process_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Determine if this webhook should be processed
        
        Purpose: Filter webhook events to only process supported ticket events
        Expected output: Boolean indicating whether to process the webhook
        """
        if not self.validate_payload_structure(webhook_data):
            return False
        
        event_type = self.get_event_type(webhook_data)
        if not event_type or not self.is_supported_event(event_type):
            logger.debug(f"Unsupported ticket event type: {event_type}")
            return False
        
        return True
    
    async def process_webhook(
        self, webhook_data: Dict[str, Any], raw_webhook_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Process Zendesk ticket webhook event
        
        Purpose: Transform Zendesk webhook data into format suitable for Port sync
        Expected output: List containing the processed ticket data
        """
        
        if not await self.should_process_webhook(webhook_data):
            return None
        
        event_type = self.get_event_type(webhook_data)
        detail = self.extract_detail_from_payload(webhook_data)
        event_data = self.extract_event_from_payload(webhook_data)
        
        if not detail:
            logger.warning(f"No detail data found in ticket webhook: {event_type}")
            return None
        
        self.log_event_processing(event_type, detail)
        
        # For ticket deletion events, we might want to handle differently
        if event_type == "zen:event-type:ticket.deleted":
            logger.info(f"Processing ticket deletion for ID: {detail.get('id')}")
            # Could implement deletion logic here if needed
        
        # Add event metadata to the ticket data
        enriched_detail = detail.copy()
        enriched_detail["webhook_event_type"] = event_type
        enriched_detail["webhook_event_data"] = event_data
        
        # Return the ticket data for synchronization
        return [enriched_detail]