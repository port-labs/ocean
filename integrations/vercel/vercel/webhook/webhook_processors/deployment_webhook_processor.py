"""Webhook processor for Vercel deployment events."""

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


class DeploymentWebhookProcessor(AbstractVercelWebhookProcessor):
    """Processes deployment-related webhook events from Vercel."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains deployment data."""
        return "deployment" in payload or "uid" in payload or "id" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event is deployment-related."""
        event_type = event.body.get("type", "")
        return event_type.startswith("deployment.")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return deployment as the affected kind."""
        return [ObjectKind.DEPLOYMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the deployment webhook event and return raw results."""
        event_type = payload.get("type", "")
        event_payload = payload.get("payload", {})
        entity_data = extract_entity(ObjectKind.DEPLOYMENT, event_payload)

        if event_type in DELETION_EVENTS:
            return await self._handle_deletion(entity_data)
        else:
            return await self._handle_upsert(entity_data, event_payload)

    async def _handle_upsert(
        self, entity_data: dict[str, Any], event_payload: dict[str, Any]
    ) -> WebhookEventRawResults:
        """Handle deployment creation/update events."""
        # Attach the project name so relations can be resolved
        project_info = event_payload.get("project", {})
        entity_data.setdefault("name", project_info.get("name"))

        logger.info(
            f"Upserting deployment entity: {entity_data.get('uid') or entity_data.get('id')}"
        )

        return WebhookEventRawResults(data_to_upsert=[entity_data], data_to_delete=[])

    async def _handle_deletion(
        self, entity_data: dict[str, Any]
    ) -> WebhookEventRawResults:
        """Handle deployment deletion events."""
        identifier = entity_data.get("uid") or entity_data.get("id")

        if not identifier:
            logger.warning(
                "Could not determine identifier for deleted deployment — skipping"
            )
            return WebhookEventRawResults(data_to_upsert=[], data_to_delete=[])

        # Construct minimal payload with correct identifier field
        deletion_payload = {"uid": identifier}

        logger.info(f"Deleting deployment entity: {identifier}")
        return WebhookEventRawResults(
            data_to_upsert=[], data_to_delete=[deletion_payload]
        )
