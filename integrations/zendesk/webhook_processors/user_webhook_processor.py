from typing import Any, cast
from loguru import logger
from initialize_client import create_zendesk_client
from zendesk.overrides import ZendeskUserResourceConfig
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


class UserWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this webhook event is a user event."""
        event_type = event.payload.get("type", "")
        return event_type in ["user.created", "user.updated", "user.deleted"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds that match this event."""
        return [Kinds.USER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle user webhook events."""
        client = create_zendesk_client()
        config = cast(ZendeskUserResourceConfig, resource_config)
        
        event_type = payload.get("type", "")
        user_data = payload.get("user", {})
        user_id = user_data.get("id")
        
        logger.info(f"Processing user webhook event: {event_type} for user ID: {user_id}")

        if event_type == "user.deleted":
            logger.info(f"User {user_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[user_data],
            )

        # For created/updated events, fetch the latest user data
        try:
            fresh_user_data = await client.get_single_user(user_id)
            
            # Apply filters based on configuration
            if not self._user_matches_filters(fresh_user_data, config):
                logger.info(f"User {user_id} doesn't match configured filters, removing from sync")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[user_data],
                )
            
            return WebhookEventRawResults(
                updated_raw_results=[fresh_user_data],
                deleted_raw_results=[],
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch user {user_id}: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    def _user_matches_filters(
        self, user: dict[str, Any], config: ZendeskUserResourceConfig
    ) -> bool:
        """Check if user matches the configured filters."""
        selector = config.selector
        
        if selector.role and user.get("role") != selector.role:
            return False
            
        if selector.organization_id and user.get("organization_id") != selector.organization_id:
            return False
            
        return True

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate webhook payload."""
        # TODO: Implement proper webhook authentication
        # For now, we'll return True to allow all webhooks
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate webhook payload structure."""
        required_fields = ["type", "user"]
        return all(field in payload for field in required_fields)