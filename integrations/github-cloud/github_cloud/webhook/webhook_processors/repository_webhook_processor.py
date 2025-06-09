from typing import Optional
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


class RepositoryWebhookProcessor(GitHubCloudAbstractWebhookProcessor):
    """
    Processor for GitHub Cloud repository events.

    Handles events related to repository creation, updates, and deletion.
    """

    # GitHub Cloud repository events
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

    def _extract_repository_data(self, payload: EventPayload) -> tuple[str, Optional[dict]]:
        """
        Extract repository data from the payload.

        Args:
            payload: Event payload

        Returns:
            Tuple of (action, repository_data)
        """
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "")

        if not repo_name:
            logger.warning("Repository full_name not found in payload")
            return action, None

        return action, repo

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

        Raises:
            ValueError: If repository data is missing or invalid
        """
        action, repo = self._extract_repository_data(payload)
        repo_name = repo.get("full_name", "") if repo else ""

        logger.info(f"Handling repository {action} event for {repo_name}")

        # Use match-case for action handling
        match action:
            case "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[repo] if repo else [],
                )
            case _:
                if not repo:
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

                try:
                    updated_repo = await self._github_cloud_webhook_client.get_repository(repo_name)
                    return WebhookEventRawResults(
                        updated_raw_results=[updated_repo] if updated_repo else [],
                        deleted_raw_results=[],
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch repository {repo_name}: {str(e)}")
                    raise ValueError(f"Failed to process repository event: {str(e)}")
