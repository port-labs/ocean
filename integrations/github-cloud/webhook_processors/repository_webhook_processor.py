from typing import Any, Dict, cast
from loguru import logger
from utils.initialize_client import get_client
from integration import ObjectKind, RepositoryResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
    EventPayload,
    EventHeaders,
)


class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    """Processor for GitHub repository webhooks."""

    ACTIONS = [
        "created",
        "deleted",
        "archived",
        "unarchived",
        "edited",
        "renamed",
        "transferred",
        "publicized",
        "privatized",
    ]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event should be processed by this handler."""
        return (
            event.headers.get("x-github-event") == "repository"
            and event.payload.get("action") in self.ACTIONS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get the kinds of events this processor handles."""
        return [ObjectKind.REPOSITORY]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        return bool(payload.get("repository"))

    async def handle_event(
        self, event: WebhookEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the repository webhook event."""
        client = get_client()
        repository = event["repository"]
        config = cast(RepositoryResourceConfig, resource_config)

        # Check if the repository's organization is in the configured organizations
        if repository["owner"]["login"] not in config.selector.organizations:
            logger.info(
                f"Skipping repository {repository['name']} from organization {repository['owner']['login']} not in configured organizations"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if event["action"] == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[repository],
            )

        updated_repo = await client.get_single_resource(
            resource_type="repos",
            owner=repository["owner"]["login"],
            repo=repository["name"],
            identifier=None,  # No identifier needed for repository
        )

        # Check if the repository visibility matches the configured visibility
        if (
            config.selector.visibility != "all"
            and updated_repo["visibility"] != config.selector.visibility
        ):
            logger.info(
                f"Skipping repository {repository['name']} with visibility {updated_repo['visibility']} not matching configured visibility {config.selector.visibility}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[updated_repo],
            deleted_raw_results=[],
        )
