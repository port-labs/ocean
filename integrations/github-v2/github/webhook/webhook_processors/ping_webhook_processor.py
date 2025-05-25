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


class PingWebhookProcessor(GitHubAbstractWebhookProcessor):
    """
    Processor for GitHub ping events.

    Handles ping events that are sent when webhooks are created or tested.
    These events help verify that webhook delivery is working correctly.
    """

    # GitHub ping events
    events = ["ping"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

        Ping events don't correspond to any specific Port entity types.

        Args:
            event: Webhook event

        Returns:
            Empty list since ping events don't map to entities
        """
        return [ObjectKind.REPOSITORY] # a default kind to pass the ProcessorManager checks.

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
        zen_message = payload.get("zen", "No zen message")
        hook_id = payload.get("hook_id")
        hook = payload.get("hook", {})
        hook_url = hook.get("config", {}).get("url", "Unknown URL")

        # Extract repository or organization info if available
        context_info = ""
        if "repository" in payload:
            repo_name = payload["repository"].get("full_name", "Unknown repository")
            context_info = f" for repository {repo_name}"
        elif "organization" in payload:
            org_name = payload["organization"].get("login", "Unknown organization")
            context_info = f" for organization {org_name}"

        logger.info(
            f"Received GitHub ping event{context_info}. "
            f"Hook ID: {hook_id}, URL: {hook_url}. "
            f"Zen: '{zen_message}'"
        )

        # Ping events don't result in any entity changes
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
        # Ping events should have a zen message and hook_id
        return "zen" in payload and "hook_id" in payload
