from typing import ClassVar, Optional
from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from github_cloud.clients.client_factory import create_github_client


class GitHubCloudAbstractWebhookProcessor(AbstractWebhookProcessor):
    """
    Abstract base class for GitHub Cloud webhook processors.

    Provides common functionality for processing GitHub Cloud webhook events.
    """

    events: ClassVar[list[str]]
    _github_cloud_webhook_client = create_github_client()

    def _get_event_type(self, headers: EventHeaders) -> Optional[str]:
        """
        Extract event type from headers.

        Args:
            headers: Event headers

        Returns:
            Event type or None if not found
        """
        return headers.get("x-github-event", "").lower()

    def _get_signature(self, headers: EventHeaders) -> Optional[str]:
        """
        Extract signature from headers.

        Args:
            headers: Event headers

        Returns:
            Signature or None if not found
        """
        return headers.get("x-hub-signature-256")

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """
        Authenticate the webhook event.

        Args:
            payload: Event payload
            headers: Event headers

        Returns:
            True if authenticated, False otherwise

        Note:
            In production, implement proper signature verification using X-Hub-Signature-256
        """
        signature = self._get_signature(headers)
        if not signature:
            logger.warning("No signature found in webhook headers")
            return False

        # TODO: Implement proper signature verification
        # For now, we'll consider all events authenticated
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Check if this processor should handle the event.

        Args:
            event: Webhook event

        Returns:
            True if this processor should handle the event, False otherwise
        """
        event_type = self._get_event_type(event.headers)
        if not event_type:
            logger.warning("No event type found in webhook headers")
            return False

        should_process = event_type in self.events
        if should_process:
            logger.debug(f"Processing {event_type} event with {self.__class__.__name__}")
        else:
            logger.debug(f"Skipping {event_type} event - not handled by {self.__class__.__name__}")

        return should_process

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise

        Note:
            Override in subclasses to implement specific validation logic
        """
        if not isinstance(payload, dict):
            logger.warning("Invalid payload type - expected dict")
            return False

        if "repository" not in payload:
            logger.warning("Missing repository in payload")
            return False

        return True
