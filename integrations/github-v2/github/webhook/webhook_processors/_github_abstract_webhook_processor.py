from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from github.clients.client_factory import create_github_client


class GitHubAbstractWebhookProcessor(AbstractWebhookProcessor):
    """
    Abstract base class for GitHub webhook processors.

    Provides common functionality for processing GitHub webhook events.
    """

    events: list[str]

    _github_webhook_client = create_github_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Authenticate the webhook event.

        Args:
            payload: Event payload
            headers: Event headers

        Returns:
            True if authenticated, False otherwise
        """
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Check if this processor should handle the event.

        Args:
            event: Webhook event

        Returns:
            True if this processor should handle the event, False otherwise
        """
        event_type = event.headers.get("x-github-event", "")
        if event_type in self.events:
            logger.info(
                f"Processing event: {event_type}, with {self.__class__.__name__}"
            )
            return True
        return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise
        """
        return "repository" in payload
