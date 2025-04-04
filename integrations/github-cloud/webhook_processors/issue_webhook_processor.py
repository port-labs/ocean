from typing import Any, Dict, cast
from loguru import logger
from initialize_client import get_client
from integration import ObjectKind, IssueResourceConfig
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


class IssueWebhookProcessor(AbstractWebhookProcessor):
    """Processor for GitHub issue webhooks."""

    ACTIONS = [
        "opened",
        "edited",
        "closed",
        "reopened",
        "deleted",
    ]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event should be processed by this handler."""
        return (
            event.headers.get("x-github-event") == "issues"
            and event.payload.get("action") in self.ACTIONS
        )

    async def get_matching_kinds(self) -> list[str]:
        return [ObjectKind.ISSUE]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        return bool(payload.get("issue") and payload.get("repository"))

    async def handle_event(
        self, event: WebhookEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the issue webhook event."""
        client = get_client()
        issue = event["issue"]
        repository = event["repository"]
        config = cast(IssueResourceConfig, resource_config)

        # Check if the repository's organization is in the configured organizations
        if repository["owner"]["login"] not in config.selector.organizations:
            logger.info(
                f"Skipping issue {issue['number']} from organization {repository['owner']['login']} not in configured organizations"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if event["action"] == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[issue],
            )

        updated_issue = await client.get_single_resource(
            resource_type="issues",
            owner=repository["owner"]["login"],
            repo=repository["name"],
            identifier=issue["number"],
        )

        # Check if the issue state matches the configured state
        if (
            config.selector.state != "all"
            and updated_issue["state"] != config.selector.state
        ):
            logger.info(
                f"Skipping issue {issue['number']} with state {updated_issue['state']} not matching configured state {config.selector.state}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[updated_issue],
            deleted_raw_results=[],
        )
