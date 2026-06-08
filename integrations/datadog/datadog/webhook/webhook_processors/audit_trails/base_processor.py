from abc import abstractmethod
from typing import Any

from httpx import HTTPStatusError
from loguru import logger
from pydantic import ValidationError

from datadog.webhook.consts import AuditTrailAction
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

    Subclasses implement three methods:
    - `_should_process`   — filter predicate on the parsed event
    - `_fetch_resource`   — live API look-up; receives the full event so processors
                            can use any field (asset id, message, http path, …)
    - `_deleted_result`   — what to put in deleted_raw_results (default: asset dict).
                            Return None to skip the delete branch and re-fetch instead
                            (used by restriction-policy processors where deleting the
                            policy does not mean the underlying resource is gone).
    """

    @staticmethod
    def parse_event(payload: Any) -> AuditTrailEvent:
        return AuditTrailEvent.parse_obj(payload)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            parsed = self.parse_event(event.payload)
        except (ValidationError, TypeError) as e:
            logger.warning(
                "Skipping unparseable audit-trail event",
                payload=event.payload,
                error=e,
            )
            return False
        return await self._should_process(parsed)

    @abstractmethod
    async def _should_process(self, event: AuditTrailEvent) -> bool:
        """Return True if this processor handles the given event."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    def _deleted_result(self, event: AuditTrailEvent) -> dict[str, Any] | None:
        """Payload for the deleted_raw_results list when action is DELETED.

        Return None to bypass the delete branch and fall through to _fetch_resource
        (e.g. when the deleted object is a wrapper, not the tracked resource itself).
        """
        return event.attributes.asset.dict()

    @abstractmethod
    async def _fetch_resource(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> dict[str, Any] | None:
        """Fetch the live resource from the Datadog API."""
        pass

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event = self.parse_event(payload)

        if event.attributes.action == AuditTrailAction.DELETED:
            deleted = self._deleted_result(event)
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[deleted] if deleted else []
            )

        resource = None
        try:
            resource = await self._fetch_resource(event, resource_config)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Resource returned 404, skipping event", error=str(e))

        return WebhookEventRawResults(
            updated_raw_results=[resource] if resource else [],
            deleted_raw_results=[],
        )
