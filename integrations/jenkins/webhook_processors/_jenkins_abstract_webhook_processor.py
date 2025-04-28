from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class _JenkinsAbstractWebhookProcessor(AbstractWebhookProcessor):
    """Abstract base class for Jenkins webhook processors."""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Jenkins authentication is handled through basic auth in the client.
        """
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
