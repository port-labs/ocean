"""
Organization webhook processor for handling organization-level GitHub events.
"""

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


class OrganizationWebhookProcessor(GitHubAbstractWebhookProcessor):
    """
    Processor for GitHub organization events.

    Handles events related to organization membership, teams, and repositories.
    """
    events = ["organization", "member", "membership", "team", "team_add", "repository"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

        Args:
            event: Webhook event

        Returns:
            List of object kinds
        """
        event_type = event.headers.get("x-github-event", "")

        match event_type:
            case "repository":
                return [ObjectKind.REPOSITORY]
            case "member" | "membership":
                return [ObjectKind.USER]
            case "team" | "team_add":
                return [ObjectKind.TEAM]
            case "organization":
                return []
            case _:
                return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle an organization event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Processing results
        """
        action = payload.get("action", "")
        event_type = payload.get("event_type", "unknown")
        org = payload.get("organization", {})
        org_name = org.get("login", "")

        logger.info(
            f"Handling organization {event_type} {action} event for {org_name}"
        )

        if "repository" in payload:
            repo = payload["repository"]
            repo_name = repo.get("full_name", "")

            logger.info(f"Repository event: {action} for {repo_name}")

            if action == "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[repo],
                )
            else:
                updated_repo = await self._github_webhook_client.get_repository(repo_name)
                updated_repo = updated_repo.json() if updated_repo.is_success else None
                return WebhookEventRawResults(
                    updated_raw_results=[updated_repo] if updated_repo else [],
                    deleted_raw_results=[],
                )

        elif "member" in payload:
            member = payload["member"]
            logger.info(f"Member event: {action} for {member.get('login', '')}")

            if action == "removed":
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[member],
                )
            else:
                member["organization"] = org
                return WebhookEventRawResults(
                    updated_raw_results=[member],
                    deleted_raw_results=[],
                )

        elif "team" in payload:
            team = payload["team"]
            team_slug = team.get("slug", "")
            logger.info(f"Team event: {action} for {team_slug}")

            if action == "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[team],
                )
            else:
                return WebhookEventRawResults(
                    updated_raw_results=[team],
                    deleted_raw_results=[],
                )
        else:
            logger.info(f"Unhandled organization event: {event_type} - {action}")
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
            True if valid, False otherwise
        """
        return "organization" in payload or any(
            key in payload for key in ["repository", "member", "team"]
        )
