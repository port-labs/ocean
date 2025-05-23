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

    # GitHub organization events
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

        if event_type == "repository":
            return [ObjectKind.REPOSITORY]
        elif event_type in ["member", "membership"]:
            return [ObjectKind.MEMBER]
        elif event_type in ["team", "team_add"]:
            return [ObjectKind.TEAM_WITH_MEMBERS]
        elif event_type == "organization":
            return []  # Organization events don't map to specific entities yet
        else:
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

        # Handle repository events at organization level
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
                # Get updated repository data
                updated_repo = await self._github_webhook_client.get_repository(repo_name)
                return WebhookEventRawResults(
                    updated_raw_results=[updated_repo] if updated_repo else [],
                    deleted_raw_results=[],
                )

        # Handle member events
        elif "member" in payload:
            member = payload["member"]
            logger.info(f"Member event: {action} for {member.get('login', '')}")

            if action == "removed":
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[member],
                )
            else:
                # Add organization context to member
                member["organization"] = org
                return WebhookEventRawResults(
                    updated_raw_results=[member],
                    deleted_raw_results=[],
                )

        # Handle team events
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
                # Enrich team with members if needed
                try:
                    enriched_team = await self._github_webhook_client.enrich_organization_with_members(
                        {**team, "organization": org},
                        team_slug,
                        include_bot_members=False
                    )
                    return WebhookEventRawResults(
                        updated_raw_results=[enriched_team],
                        deleted_raw_results=[],
                    )
                except Exception as e:
                    logger.warning(f"Could not enrich team {team_slug}: {e}")
                    team["organization"] = org
                    return WebhookEventRawResults(
                        updated_raw_results=[team],
                        deleted_raw_results=[],
                    )

        # Handle other organization events
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
