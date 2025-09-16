"""Webhook processor for Okta group events."""

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from .okta_base_webhook_processor import OktaBaseWebhookProcessor
from okta.core.options import GetGroupOptions


class GroupWebhookProcessor(OktaBaseWebhookProcessor):
    """Webhook processor for Okta group events."""

    # Group-related event types
    GROUP_EVENTS = [
        "group.lifecycle.create",
        "group.lifecycle.update",
        "group.lifecycle.delete",
        "group.user_membership.add",
        "group.user_membership.remove",
        "group.user_membership.add.end",
        "group.user_membership.remove.end",
    ]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this is a group-related event.
        
        Args:
            event: The webhook event
            
        Returns:
            True if this is a group event, False otherwise
        """
        event_type = event.payload.get("eventType", "")
        return event_type in self.GROUP_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get the resource kinds that this event affects.
        
        Args:
            event: The webhook event
            
        Returns:
            List of resource kinds
        """
        return ["okta-group"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the group webhook event.
        
        Args:
            payload: The webhook payload
            resource_config: The resource configuration
            
        Returns:
            Webhook event results
        """
        from okta.core.exporters.group_exporter import OktaGroupExporter
        
        exporter = OktaGroupExporter(self.client)
        
        # Extract group ID from the event
        group_id = self._extract_group_id(payload)
        if not group_id:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
        
        event_type = payload.get("eventType", "")
        
        # Handle deletion events
        if "delete" in event_type:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": group_id}],
            )
        
        # For create/update/membership events, fetch the current group data
        try:
            options = GetGroupOptions(
                group_id=group_id,
                include_members=True,
            )
            
            group_data = await exporter.get_resource(options)
            
            return WebhookEventRawResults(
                updated_raw_results=[group_data],
                deleted_raw_results=[],
            )
        except Exception as e:
            # If we can't fetch the group, it might have been deleted
            # Return it as a deletion
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": group_id}],
            )

    def _extract_group_id(self, payload: EventPayload) -> str | None:
        """Extract group ID from the event payload.
        
        Args:
            payload: The webhook payload
            
        Returns:
            Group ID if found, None otherwise
        """
        # Try to extract from target array
        targets = payload.get("target", [])
        for target in targets:
            if target.get("type") == "UserGroup":
                return target.get("id")
        
        # Try to extract from debug context
        debug_context = payload.get("debugContext", {})
        return debug_context.get("group", {}).get("id") if "group" in debug_context else None
