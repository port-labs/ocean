from typing import cast

from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from aws.core.helpers.metadata.types import NormalizedEvent
from aws.webhook.input_transformer_parser import (
    InputTransformerPayload,
    is_input_transformer_event,
    parse_input_transformer_event,
)
from aws.webhook.webhook_processors.live_events_webhook_processor import (
    LiveEventsWebhookProcessor,
)


class InputTransformerWebhookProcessor(LiveEventsWebhookProcessor):
    """Handles live events whose resource type and identifier were set by the customer's EventBridge rule."""

    def _parse_event(self, payload: EventPayload) -> NormalizedEvent | None:
        return parse_input_transformer_event(cast(InputTransformerPayload, payload))

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return is_input_transformer_event(cast(InputTransformerPayload, event.payload))
