from abc import abstractmethod
from typing import Any

from loguru import logger
from pydantic import ValidationError

from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class BaseAuditTrailProcessor(BaseWebhookProcessor):
    """Base for all audit-trail webhook processors.

    Each WebhookEvent carries exactly one event dict — batches are split
    upstream by DatadogLiveEventsProcessorManager.

    Subclasses implement _should_process and _handle_audit_event, which
    receive an already-parsed AuditTrailEvent so they never touch raw dicts.
    """

    @staticmethod
    def parse_event(payload: Any) -> AuditTrailEvent:
        return AuditTrailEvent.parse_obj(payload)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            parsed = self.parse_event(event.payload)
        except (ValidationError, TypeError):
            logger.debug(f"Skipping unparseable audit-trail payload: {event.payload}")
            return False
        return await self._should_process(parsed)

    @abstractmethod
    async def _should_process(self, event: AuditTrailEvent) -> bool:
        """Return True if this processor handles the given event."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return await self._handle_audit_event(
            self.parse_event(payload), resource_config
        )

    @abstractmethod
    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the parsed audit-trail event."""
