from typing import cast
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.webhook_processors.events import RepositoryEvents
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    _BitbucketAbstractWebhookProcessor,
)
from integration import RepositoryResourceConfig
from loguru import logger


class RepositoryWebhookProcessor(_BitbucketAbstractWebhookProcessor):

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        try:
            return bool(RepositoryEvents(event.headers["x-event-key"]))
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        repository_id = payload["repository"]["uuid"]
        logger.info(
            f"Handling repository webhook event for repository: {repository_id}"
        )
        repository_details = await self._webhook_client.get_repository(repository_id)

        selector = cast(RepositoryResourceConfig, resource_config).selector
        included_files = selector.included_files or []
        if included_files:
            from bitbucket_cloud.enrichments.included_files import (
                IncludedFilesEnricher,
                RepositoryIncludedFilesStrategy,
            )

            enricher = IncludedFilesEnricher(
                client=self._webhook_client,
                strategy=RepositoryIncludedFilesStrategy(included_files=included_files),
            )
            repository_details = (await enricher.enrich_batch([repository_details]))[0]

        return WebhookEventRawResults(
            updated_raw_results=[repository_details],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        required_field = "repository"
        return required_field in payload
