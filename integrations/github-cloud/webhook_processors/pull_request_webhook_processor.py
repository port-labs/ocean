from typing import Any, Dict, cast
from loguru import logger
from utils.initialize_client import get_client
from integration import ObjectKind, PullRequestResourceConfig
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


class PullRequestWebhookProcessor(AbstractWebhookProcessor):
    """Processor for GitHub pull request webhooks."""

    ACTIONS = [
        "opened",
        "edited",
        "closed",
        "reopened",
        "merged",
        "synchronize",
    ]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event should be processed by this handler."""
        return (
            event.headers.get("x-github-event") == "pull_request"
            and event.payload.get("action") in self.ACTIONS
        )

    async def get_matching_kinds(self) -> list[str]:
        """Get the kinds of events this processor handles."""
        return [ObjectKind.PULL_REQUEST]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        return bool(payload.get("pull_request") and payload.get("repository"))

    async def handle_event(
        self, event: WebhookEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the pull request webhook event."""
        client = get_client()
        pull_request = event["pull_request"]
        repository = event["repository"]
        config = cast(PullRequestResourceConfig, resource_config)

        # Check if the repository's organization is in the configured organizations
        if repository["owner"]["login"] not in config.selector.organizations:
            logger.info(
                f"Skipping pull request {pull_request['number']} from organization {repository['owner']['login']} not in configured organizations"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if event["action"] == "closed" and not pull_request.get("merged"):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[pull_request],
            )

        updated_pr = await client.get_single_resource(
            resource_type="pulls",
            owner=repository["owner"]["login"],
            repo=repository["name"],
            identifier=pull_request["number"],
        )

        # Check if the pull request state matches the configured state
        if (
            config.selector.state != "all"
            and updated_pr["state"] != config.selector.state
        ):
            logger.info(
                f"Skipping pull request {pull_request['number']} with state {updated_pr['state']} not matching configured state {config.selector.state}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[updated_pr],
            deleted_raw_results=[],
        )
