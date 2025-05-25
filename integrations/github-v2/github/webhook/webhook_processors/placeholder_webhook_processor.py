from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    GitHubAbstractWebhookProcessor,
)


class PlaceholderWebhookProcessor(GitHubAbstractWebhookProcessor):
    """
    Processor for GitHub ping events.

    "Handles events that don't correspond to any specific Port entity types."
    """

    # GitHub ping events
    events = ["ping", 'workflow_run', 'workflow_job', 'push']

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

       Any event's that don't correspond to any specific Port entity types. ObjectKind.REPOSITORY is used as a placeholder.

        Args:
            event: Webhook event

        Returns:
            Empty list since ping events don't map to entities
        """
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle a ping event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Empty processing results since ping events don't create/update entities
        """

        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid ping payload, False otherwise
        """

        return True
