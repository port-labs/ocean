from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github_cloud.helpers.utils import ObjectKind
from github_cloud.webhook.webhook_processors._github_abstract_webhook_processor import (
    GitHubCloudAbstractWebhookProcessor,
)


class PullRequestWebhookProcessor(GitHubCloudAbstractWebhookProcessor):
    """
    Processor for GitHub Cloud pull request events.

    Handles events related to pull request creation, updates, and closure.
    """

    # GitHub Cloud pull request events
    events = ["pull_request"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

        Args:
            event: Webhook event

        Returns:
            List of object kinds
        """
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle a pull request event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Processing results
        """
        action = payload.get("action", "")
        pull_request = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")
        pr_number = pull_request.get("number")

        logger.info(
            f"Handling pull request {action} event for {repo_name}#{pr_number}"
        )

        # Get the full pull request data from the API
        updated_pr = await self._github_cloud_webhook_client.get_pull_request(
            repo_name, pr_number
        )

        if not updated_pr:
            logger.warning(f"Could not fetch pull request {repo_name}#{pr_number}")
            # If we can't fetch the PR, use the one from the payload
            updated_pr = pull_request

        # Add repository information to the pull request
        updated_pr["repository"] = repo

        return WebhookEventRawResults(
            updated_raw_results=[updated_pr],
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
        return "pull_request" in payload and "repository" in payload
