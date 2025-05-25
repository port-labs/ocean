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


class RepositoryWebhookProcessor(GitHubAbstractWebhookProcessor):
    """
    Processor for GitHub repository events.

    Handles events related to repository creation, updates, and deletion.
    """

    events = ["repository"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """
        Get the matching object kinds for this event.

        Args:
            event: Webhook event

        Returns:
            List of object kinds
        """
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle a repository event.

        Args:
            payload: Event payload
            resource_config: Resource configuration

        Returns:
            Processing results
        """
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")

        logger.info(
            f"Handling repository {action} event for {repo_name}"
        )

        # For repository deletion, return it in deleted_raw_results
        if action == "deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[repo],
            )

        repo_full_name = repo.get("full_name", "")

        if not repo_full_name:
            logger.warning("Repository full_name not found in payload")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        updated_repo = await self._github_webhook_client.get_repository(repo_full_name)
        updated_repo = updated_repo.json() if updated_repo else None
        return WebhookEventRawResults(
            updated_raw_results=[updated_repo] if updated_repo else [],
            deleted_raw_results=[],
        )
