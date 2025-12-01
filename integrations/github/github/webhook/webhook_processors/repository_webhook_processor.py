from typing import cast
from loguru import logger
from github.webhook.events import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import GithubRepositoryConfig
from github.core.options import (
    SingleRepositoryOptions,
)
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)


class RepositoryWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        action = payload.get("action")
        if not action:
            return False

        valid_actions = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        return action in valid_actions

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "repository"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        repo = payload["repository"]
        name = repo["name"]
        organization = payload["organization"]["login"]
        resource_config = cast(GithubRepositoryConfig, resource_config)

        logger.info(
            f"Processing repository event: {action} for {name} from {organization}"
        )

        if resource_config.selector.repo_search is not None:
            logger.info(
                "search query is configured for this kind, checking if repository is in matched results."
            )
            repo = await self.repo_in_search(payload, resource_config)
            if repo is None:
                logger.info(
                    "Repository is not matched by search query, no actions will be performed."
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

        if action in REPOSITORY_DELETE_EVENTS:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[repo]
            )

        rest_client = create_github_client()
        exporter = RestRepositoryExporter(rest_client)

        options = SingleRepositoryOptions(
            organization=organization,
            name=name,
            included_relationships=cast(list[str], resource_config.selector.include),
        )

        data_to_upsert = await exporter.get_resource(options)

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
