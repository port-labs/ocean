from typing import Optional, Tuple
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

    def _extract_pull_request_data(self, payload: EventPayload) -> Tuple[str, dict, dict, Optional[int]]:
        """
        Extract pull request data from the payload.

        Args:
            payload: Event payload

        Returns:
            Tuple of (action, pull_request_data, repository_data, pr_number)

        Raises:
            ValueError: If required data is missing
        """
        action = payload.get("action", "")
        pull_request = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")
        pr_number = pull_request.get("number")

        if not repo_name or not pr_number:
            raise ValueError(
                f"Missing required data in payload: repo_name={repo_name}, pr_number={pr_number}"
            )

        return action, pull_request, repo, pr_number

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

        Raises:
            ValueError: If required data is missing or invalid
        """
        try:
            action, pull_request, repo, pr_number = self._extract_pull_request_data(payload)
            repo_name = repo.get("full_name", "")

            logger.info(f"Handling pull request {action} event for {repo_name}#{pr_number}")

            # Use match-case for action handling
            match action:
                case "closed" | "merged":
                    # For closed/merged PRs, we still want to update the status
                    updated_pr = await self._github_cloud_webhook_client.get_pull_request(
                        repo_name, pr_number
                    )
                case _:
                    # For other actions, try to get fresh data, fallback to payload
                    updated_pr = (
                        await self._github_cloud_webhook_client.get_pull_request(repo_name, pr_number)
                        or pull_request
                    )

            if not updated_pr:
                logger.warning(f"Could not fetch pull request {repo_name}#{pr_number}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

            # Add repository information to the pull request
            updated_pr["repository"] = repo

            return WebhookEventRawResults(
                updated_raw_results=[updated_pr],
                deleted_raw_results=[],
            )

        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to process pull request event: {str(e)}")
            raise ValueError(f"Failed to process pull request event: {str(e)}")

    async def validate_payload(self, payload: EventPayload) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise
        """
        try:
            self._extract_pull_request_data(payload)
            return True
        except ValueError:
            return False
