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
        event_type = event.payload.get("action")
        event = event.headers.get("x-github-event")

        return (
            event == "repository"
            and event_type in REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload.get("action")
        repo = payload.get("repository", {})
        repo_name = repo["name"]

        logger.info(f"Processing repository event: {action} for {repo_name}")

        if action in REPOSITORY_DELETE_EVENTS:
            logger.info(f"Repository {repo_name} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[repo]
            )

        client = GitHubClient.from_ocean_config()
        latest_repo = await client.get_single_resource(ObjectKind.REPOSITORY, repo_name)

        return WebhookEventRawResults(
            updated_raw_results=[latest_repo], deleted_raw_results=[]
        )
