from typing import Dict, Any
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from github_cloud.helpers.utils import ObjectKind
from github_cloud.webhook.webhook_processors._github_abstract_webhook_processor import GitHubCloudAbstractWebhookProcessor


class IssueWebhookProcessor(GitHubCloudAbstractWebhookProcessor):
    """
    Processor for GitHub issue webhook events.
    Handles issue creation, updates, and closure.
    """

    def __init__(self, event: WebhookEvent) -> None:
        """
        Initialize the issue webhook processor.

        Args:
            event: Webhook event
        """
        super().__init__(event)
        self.events = ["issues", "issue_comment"]

    def get_matching_kinds(self) -> set[str]:
        """
        Get the kinds of entities this processor can handle.

        Returns:
            Set of entity kinds
        """
        return {ObjectKind.ISSUE}

    async def handle_event(self, payload=None, resource_config: ResourceConfig = None) -> WebhookEventRawResults:
        """
        Handle the webhook event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            WebhookEventRawResults containing the processed results
        """
        if payload is None:
            payload = self.event.payload
        if not await self.should_process_event(self.event):
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
        if not await self.validate_payload(payload):
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Get the issue data from the payload
        issue = payload["issue"]
        repo_name = payload["repository"]["full_name"]
        issue_number = issue["number"]

        # Try to fetch fresh data from GitHub
        updated_issue = await self._github_cloud_webhook_client.get_issue(repo_name, issue_number)
        if updated_issue:
            # Enrich with repository data
            updated_issue["repository"] = payload["repository"]
            return WebhookEventRawResults(updated_raw_results=[updated_issue], deleted_raw_results=[])

        # Fallback to payload data if fetch fails
        issue["repository"] = payload["repository"]
        return WebhookEventRawResults(updated_raw_results=[issue], deleted_raw_results=[])

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """
        Validate the webhook payload.

        Args:
            payload: Event payload

        Returns:
            True if valid, False otherwise
        """
        return "issue" in payload and "repository" in payload
