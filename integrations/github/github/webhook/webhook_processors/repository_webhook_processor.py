from typing import cast
from loguru import logger
from github.webhook.events import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from github.helpers.utils import GithubClientType, ObjectKind
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
    GraphQLRepositorySelectorOptions,
    SingleGraphQLRepositoryOptions,
    SingleRepositoryOptions,
)
from github.core.exporters.repository_exporter import (
    GraphQLRepositoryExporter,
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

        logger.info(f"Processing repository event: {action} for {name}")

        if action in REPOSITORY_DELETE_EVENTS:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[repo]
            )

        config = cast(GithubRepositoryConfig, resource_config)
        graphql_required_selectors = [
            config.selector.collaborators,
            config.selector.teams,
            config.selector.custom_properties,
        ]

        if any(graphql_required_selectors):
            logger.info(
                "Using GraphQL client with collaborators exporter for handling repository webhook"
            )
            graphql_client = create_github_client(GithubClientType.GRAPHQL)
            graphql_exporter = GraphQLRepositoryExporter(graphql_client)
            graphql_options = SingleGraphQLRepositoryOptions(
                name=name,
                selector=cast(
                    GraphQLRepositorySelectorOptions,
                    config.selector.dict(exclude_unset=True),
                ),
            )
            data_to_upsert = await graphql_exporter.get_resource(graphql_options)
        else:
            logger.info(
                "Using REST client with repository exporter for handling repository webhook"
            )
            rest_client = create_github_client()
            rest_exporter = RestRepositoryExporter(rest_client)
            rest_options = SingleRepositoryOptions(name=name)
            data_to_upsert = await rest_exporter.get_resource(rest_options)

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
