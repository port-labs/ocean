"""Webhook processor for Vercel project events."""

from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from vercel.helpers.utils import ObjectKind, extract_entity
from vercel.webhook.events import DELETION_EVENTS
from vercel.webhook.webhook_processors.abstract_webhook_processor import (
    AbstractVercelWebhookProcessor,
)


class ProjectWebhookProcessor(AbstractVercelWebhookProcessor):
    """Processes project-related webhook events from Vercel."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains project data."""
        return "project" in payload or "id" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is project-related."""
        event_type = event.body.get("type", "")
        return event_type.startswith("project.")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return project as the affected kind."""
        return [ObjectKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the project webhook event and return raw results."""
        event_type = payload.get("type", "")
        event_payload = payload.get("payload", {})
        entity_data = extract_entity(ObjectKind.PROJECT, event_payload)

        if event_type in DELETION_EVENTS:
            return await self._handle_deletion(entity_data)
        else:
            return await self._handle_upsert(entity_data)

    async def _handle_upsert(
        self, entity_data: dict[str, Any]
    ) -> WebhookEventRawResults:
        """Handle project creation events."""
        logger.info(f"Upserting project entity: {entity_data.get('id')}")
        return WebhookEventRawResults(data_to_upsert=[entity_data], data_to_delete=[])

    async def _handle_deletion(
        self, entity_data: dict[str, Any]
    ) -> WebhookEventRawResults:
        """Handle project deletion events."""
        identifier = entity_data.get("id")

        if not identifier:
            logger.warning(
                "Could not determine identifier for deleted project — skipping"
            )
            return WebhookEventRawResults(data_to_upsert=[], data_to_delete=[])

        deletion_payload = {"id": identifier}

        logger.info(f"Deleting project entity: {identifier}")
        return WebhookEventRawResults(
            data_to_upsert=[], data_to_delete=[deletion_payload]
        )
