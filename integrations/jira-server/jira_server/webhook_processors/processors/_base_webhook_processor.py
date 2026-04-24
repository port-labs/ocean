from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, EventHeaders


class _BaseJiraWebhookProcessor(AbstractWebhookProcessor):
    """Base class for Jira webhook processors"""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """No authentication required for Jira webhooks"""
        return True
