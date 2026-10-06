from pydantic.v1 import ValidationError

from newrelic_integration.core.issues import IssueEvent
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class BaseWebhookProcessor(AbstractWebhookProcessor):
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return await self.validate_payload(event.payload)

    async def validate_payload(self, payload: EventPayload) -> bool:
        try:
            IssueEvent(**payload)
            return True
        except (ValidationError, TypeError):
            return False
