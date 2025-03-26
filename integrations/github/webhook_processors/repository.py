from loguru import logger
from client import GitHubClient
from consts import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from helpers.utils import ObjectKind
from webhook_processors.abstract import GitHubAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

class RepositoryWebhookProcessor(GitHubAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if this event should be processed."""
        event_type = event.payload.get("action")
        return (
            event.payload.get("repository") is not None
            and event_type in REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = GitHubClient.from_ocean_config()
        repo = payload.get("repository", {})
        repo_name = repo.get("name")

        if payload.get("action") in REPOSITORY_DELETE_EVENTS:
            logger.info(f"Repository {repo_name} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[repo],
            )

        logger.info(f"Got event for repository {repo_name}: {payload.get('action')}")
        updated_repo = await client.get_repositories(repo_name)

        return WebhookEventRawResults(
            updated_raw_results=[updated_repo],
            deleted_raw_results=[],
        ) 