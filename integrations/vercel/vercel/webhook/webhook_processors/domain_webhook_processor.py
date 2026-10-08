"""Webhook processor for Vercel domain events."""

from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from vercel.helpers.utils import ObjectKind
from vercel.webhook.events import DELETION_EVENTS
from vercel.webhook.webhook_processors.abstract_webhook_processor import (
    AbstractVercelWebhookProcessor,
)


class DomainWebhookProcessor(AbstractVercelWebhookProcessor):
    """Processes domain-related webhook events from Vercel."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains domain data."""
        return "domain" in payload or "name" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is domain-related."""
        event_type = event.payload.get("type", "")
        return event_type.startswith("domain.")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return domain as the affected kind."""
        return [ObjectKind.DOMAIN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the domain webhook event and return raw results."""
        event_type = payload.get("type", "")
        event_payload = payload.get("payload", {})
        entity_data = event_payload.get("domain", event_payload)

        if event_type in DELETION_EVENTS:
            return await self._handle_deletion(entity_data)
        else:
            return await self._handle_upsert(entity_data)

    async def _handle_upsert(
        self, entity_data: dict[str, Any]
    ) -> WebhookEventRawResults:
        """Handle domain creation events."""
        logger.info(f"Upserting domain entity: {entity_data.get('name')}")
        return WebhookEventRawResults(updated_raw_results=[entity_data], deleted_raw_results=[])

    async def _handle_deletion(
        self, entity_data: dict[str, Any]
    ) -> WebhookEventRawResults:
        """Handle domain deletion events."""
        identifier = entity_data.get("name")

        if not identifier:
            logger.warning(
                "Could not determine identifier for deleted domain — skipping"
            )
            return WebhookEventRawResults(data_to_upsert=[], data_to_delete=[])

        deletion_payload = {"name": identifier}

        logger.info(f"Deleting domain entity: {identifier}")
        return WebhookEventRawResults(
            data_to_upsert=[], data_to_delete=[deletion_payload]
        )
