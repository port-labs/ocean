from loguru import logger
from github_cloud.helpers.constants import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from github_cloud.helpers.utils import ObjectKind
from initialize_client import init_client
from github_cloud.webhook_processors.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")

        return (
            event_name == "repository" and event_type in REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload.get("action")
        repository = payload.get("repository", {})
        repo_name = repository.get("name")

        logger.info(f"Processing repository event: {action} for {repo_name}")

        if action in REPOSITORY_DELETE_EVENTS:
            logger.info(f"Repository {repo_name} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[repository],
            )

        client = init_client()
        latest_repo = await client.get_single_resource(ObjectKind.REPOSITORY, repo_name)

        logger.info(f"Successfully retrieved recent data for repository {repo_name}")

        return WebhookEventRawResults(updated_raw_results=[latest_repo], deleted_raw_results=[])
