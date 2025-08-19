from typing import Any, cast
from loguru import logger
from initialize_client import create_zendesk_client
from zendesk.overrides import ZendeskOrganizationResourceConfig
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


class OrganizationWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this webhook event is an organization event."""
        event_type = event.payload.get("type", "")
        return event_type in ["organization.created", "organization.updated", "organization.deleted"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds that match this event."""
        return [Kinds.ORGANIZATION]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle organization webhook events."""
        client = create_zendesk_client()
        config = cast(ZendeskOrganizationResourceConfig, resource_config)
        
        event_type = payload.get("type", "")
        organization_data = payload.get("organization", {})
        organization_id = organization_data.get("id")
        
        logger.info(f"Processing organization webhook event: {event_type} for organization ID: {organization_id}")

        if event_type == "organization.deleted":
            logger.info(f"Organization {organization_id} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[organization_data],
            )

        # For created/updated events, fetch the latest organization data
        try:
            fresh_organization_data = await client.get_single_organization(organization_id)
            
            # Apply filters based on configuration
            if not self._organization_matches_filters(fresh_organization_data, config):
                logger.info(f"Organization {organization_id} doesn't match configured filters, removing from sync")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[organization_data],
                )
            
            return WebhookEventRawResults(
                updated_raw_results=[fresh_organization_data],
                deleted_raw_results=[],
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch organization {organization_id}: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

    def _organization_matches_filters(
        self, organization: dict[str, Any], config: ZendeskOrganizationResourceConfig
    ) -> bool:
        """Check if organization matches the configured filters."""
        selector = config.selector
        
        if selector.external_id and organization.get("external_id") != selector.external_id:
            return False
            
        return True

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate webhook payload."""
        # TODO: Implement proper webhook authentication
        # For now, we'll return True to allow all webhooks
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate webhook payload structure."""
        required_fields = ["type", "organization"]
        return all(field in payload for field in required_fields)