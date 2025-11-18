from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import ObjectKind
from webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)
from webhook_processors.webhook_client import REPO_WEBHOOK_EVENTS


class RepositoryWebhookProcessor(BaseWebhookProcessorMixin):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload["eventKey"] in REPO_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        event_key = payload.get("eventKey", "")
        if event_key == "repo:refs_changed":
            repository_slug = payload["repository"]["slug"]
            project_key = payload["repository"]["project"]["key"]
        else:
            repository_slug = payload["new"]["slug"]
            project_key = payload["new"]["project"]["key"]

        logger.info(
            f"Handling repository webhook event ({event_key}) for project: {project_key} and repository: {repository_slug}"
        )

        repository = await self._client.get_single_repository(
            project_key=project_key, repo_slug=repository_slug
        )

        return WebhookEventRawResults(
            updated_raw_results=[repository],
            deleted_raw_results=[],
        )
