from typing import Any, cast
from loguru import logger
from initialize_client import create_zendesk_client
from zendesk.overrides import ZendeskTicketResourceConfig
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class TicketWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this webhook event is a ticket event."""
        event_type = event.payload.get("type", "")
        return event_type in ["ticket.created", "ticket.updated", "ticket.deleted"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds that match this event."""
        return [Kinds.TICKET]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle ticket webhook events."""
        client = create_zendesk_client()
        config = cast(ZendeskTicketResourceConfig, resource_config)
        
        event_type = payload.get("type", "")
        ticket_data = payload.get("ticket", {})
        ticket_id = ticket_data.get("id")
        
        logger.info(f"Processing ticket webhook event: {event_type} for ticket ID: {ticket_id}")

        if event_type == "ticket.deleted":
            logger.info(f"Ticket {ticket_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[ticket_data],
            )

        # For created/updated events, fetch the latest ticket data
        try:
            fresh_ticket_data = await client.get_single_ticket(ticket_id)
            
            # Apply filters based on configuration
            if not self._ticket_matches_filters(fresh_ticket_data, config):
                logger.info(f"Ticket {ticket_id} doesn't match configured filters, removing from sync")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[ticket_data],
                )
            
            return WebhookEventRawResults(
                updated_raw_results=[fresh_ticket_data],
                deleted_raw_results=[],
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch ticket {ticket_id}: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    def _ticket_matches_filters(
        self, ticket: dict[str, Any], config: ZendeskTicketResourceConfig
    ) -> bool:
        """Check if ticket matches the configured filters."""
        selector = config.selector
        
        if selector.status and ticket.get("status") != selector.status:
            return False
            
        if selector.priority and ticket.get("priority") != selector.priority:
            return False
            
        if selector.assignee_id and ticket.get("assignee_id") != selector.assignee_id:
            return False
            
        if selector.organization_id and ticket.get("organization_id") != selector.organization_id:
            return False
            
        return True

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate webhook payload."""
        # TODO: Implement proper webhook authentication
        # For now, we'll return True to allow all webhooks
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate webhook payload structure."""
        required_fields = ["type", "ticket"]
        return all(field in payload for field in required_fields)