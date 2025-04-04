from typing import Any, Dict, cast
from loguru import logger
from client import get_client
from integration import ObjectKind, TeamResourceConfig
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


class TeamWebhookProcessor(AbstractWebhookProcessor):
    """Processor for GitHub team webhooks."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event should be processed."""
        return event.get("action") in [
            "created",
            "deleted",
            "edited",
            "added_to_repository",
            "removed_from_repository",
        ]

    async def get_matching_kinds(self) -> list[str]:
        """Get the kinds of events this processor handles."""
        return [ObjectKind.TEAM]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload."""
        return bool(payload.get("team") and payload.get("organization"))

    async def handle_event(
        self, event: WebhookEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle the team webhook event."""
        client = get_client()
        team = event["team"]
        organization = event["organization"]
        config = cast(TeamResourceConfig, resource_config)

        # Check if the organization is in the configured organizations
        if organization["login"] not in config.selector.organizations:
            logger.info(
                f"Skipping team {team['name']} from organization {organization['login']} not in configured organizations"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if event["action"] == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[team],
            )

        updated_team = await client.get_single_resource(
            resource_type="teams",
            owner=organization["login"],
            repo=None,  # No repo needed for teams
            identifier=team["slug"],
        )

        return WebhookEventRawResults(
            updated_raw_results=[updated_team],
            deleted_raw_results=[],
        )
