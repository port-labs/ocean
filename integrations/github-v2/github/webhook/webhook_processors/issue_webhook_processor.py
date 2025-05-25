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


class IssueWebhookProcessor(GitHubAbstractWebhookProcessor):
    """
    Processor for GitHub issue events.

    Handles events related to issue creation, updates, and closure.
    """

    # GitHub issue events
    events = ["issues"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

        Args:
            event: Webhook event

        Returns:
            List of object kinds
        """
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle an issue event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Processing results
        """
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")
        issue_number = issue.get("number")

        logger.info(
            f"Handling issue {action} event for {repo_name}#{issue_number}"
        )

        # For issue deletion, return it in deleted_raw_results
        if action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[issue],
            )

        # Get the full issue data from the API
        updated_issue = await self._github_webhook_client.get_issue(
            repo_name, issue_number
        )

        updated_issue = updated_issue.json() if updated_issue else None
        if not updated_issue:
            logger.warning(f"Could not fetch issue {repo_name}#{issue_number}")
            updated_issue = issue


        updated_issue["repository"] = repo

        return WebhookEventRawResults(
            updated_raw_results=[updated_issue],
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
        return "issue" in payload and "repository" in payload
