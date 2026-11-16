"""Unified CloudTrail live-events webhook processor.

All supported kinds share one processor. Per-kind behavior is delegated to
``cloudtrail_parser`` (event normalization) and ``kind_to_export_metadata``
(fetch and delete payloads).
"""

from typing import cast

from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from aws.core.helpers.metadata.types import NormalizedEvent
from aws.webhook.cloudtrail_parser import (
    EventBridgeCloudTrailPayload,
    is_supported_cloudtrail_event,
    parse_cloudtrail_event,
)
from aws.webhook.webhook_processors.live_events_webhook_processor import (
    LiveEventsWebhookProcessor,
)


class CloudTrailWebhookProcessor(LiveEventsWebhookProcessor):
    """Handles CloudTrail live events for all registered resource kinds."""

    def _parse_event(self, payload: EventPayload) -> NormalizedEvent | None:
        return parse_cloudtrail_event(cast(EventBridgeCloudTrailPayload, payload))

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return is_supported_cloudtrail_event(
            cast(EventBridgeCloudTrailPayload, event.payload)
        )
