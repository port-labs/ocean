from typing import Any, Dict, List, Optional

from loguru import logger
from port_ocean.context.event import event

from webhook_processors.base_webhook_processor import ZendeskBaseWebhookProcessor

"""
User webhook processor for Zendesk user events

Based on Zendesk webhook event types documentation:
https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/

Purpose: Process real-time webhook events for Zendesk users
Expected output: Processed user data for Port synchronization
"""


class UserWebhookProcessor(ZendeskBaseWebhookProcessor):
    """
    Webhook processor for Zendesk user events
    
    Handles user-related webhook events including:
    - User creation, updates, deletion
    - Role changes
    - Status changes (active/suspended)
    - Profile updates
    """
    
    def get_supported_events(self) -> List[str]:
        """
        Get list of supported user event types
        
        Based on: https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/
        
        Returns:
            List of Zendesk user event type strings
        """
        return [
            "zen:event-type:user.created",
            "zen:event-type:user.updated",
            "zen:event-type:user.deleted",
            "zen:event-type:user.role_changed",
            "zen:event-type:user.suspended",
            "zen:event-type:user.unsuspended",
            "zen:event-type:user.activated",
            "zen:event-type:user.identity_created",
            "zen:event-type:user.identity_updated",
            "zen:event-type:user.identity_deleted",
        ]
    
    async def should_process_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Determine if this webhook should be processed
        
        Purpose: Filter webhook events to only process supported user events
        Expected output: Boolean indicating whether to process the webhook
        """
        if not self.validate_payload_structure(webhook_data):
            return False
        
        event_type = self.get_event_type(webhook_data)
        if not event_type or not self.is_supported_event(event_type):
            logger.debug(f"Unsupported user event type: {event_type}")
            return False
        
        return True
    
    async def process_webhook(
        self, webhook_data: Dict[str, Any], raw_webhook_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Process Zendesk user webhook event
        
        Purpose: Transform Zendesk webhook data into format suitable for Port sync
        Expected output: List containing the processed user data
        """
        
        if not await self.should_process_webhook(webhook_data):
            return None
        
        event_type = self.get_event_type(webhook_data)
        detail = self.extract_detail_from_payload(webhook_data)
        event_data = self.extract_event_from_payload(webhook_data)
        
        if not detail:
            logger.warning(f"No detail data found in user webhook: {event_type}")
            return None
        
        self.log_event_processing(event_type, detail)
        
        # For user deletion events, we might want to handle differently
        if event_type == "zen:event-type:user.deleted":
            logger.info(f"Processing user deletion for ID: {detail.get('id')}")
            # Could implement deletion logic here if needed
        
        # For role changes, log the change for visibility
        if event_type == "zen:event-type:user.role_changed" and event_data:
            old_role = event_data.get("previous")
            new_role = event_data.get("current")
            logger.info(f"User {detail.get('id')} role changed from {old_role} to {new_role}")
        
        # Add event metadata to the user data
        enriched_detail = detail.copy()
        enriched_detail["webhook_event_type"] = event_type
        enriched_detail["webhook_event_data"] = event_data
        
        # Return the user data for synchronization
        return [enriched_detail]