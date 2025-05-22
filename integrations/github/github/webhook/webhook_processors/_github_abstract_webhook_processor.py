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
        # GitHub sends a X-GitHub-Event header with the event name
        # For simplicity, we'll consider all events authenticated
        # In production, you'd verify the signature in X-Hub-Signature-256
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Check if this processor should handle the event.

        Args:
            event: Webhook event

        Returns:
            True if this processor should handle the event, False otherwise
        """
        # GitHub sends the event type in X-GitHub-Event header
        event_type = event.headers.get("x-github-event", "")
        return event_type in self.events

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise
        """
        # Basic validation checking for common fields
        # Override in subclasses as needed
        return "repository" in payload
