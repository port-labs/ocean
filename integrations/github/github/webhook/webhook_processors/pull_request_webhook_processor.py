from typing import Any, cast
from loguru import logger
from github.webhook.events import PULL_REQUEST_EVENTS
from github.helpers.utils import (
    GithubClientType,
    ObjectKind,
    enrich_with_organization,
    enrich_with_repository,
)
from github.clients.client_factory import create_github_client
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.exporters.pull_request_exporter import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
from github.core.options import SinglePullRequestOptions
from integration import GithubPullRequestConfig
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)


class PullRequestWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "pull_request" in payload and "number" in payload["pull_request"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "pull_request"
            and event.payload.get("action") in PULL_REQUEST_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        pull_request = payload["pull_request"]
        number = pull_request["number"]
        repo = payload["repository"]
        repo_name = repo["name"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubPullRequestConfig, resource_config)

        logger.info(
            f"Processing pull request event: {action} for {repo_name}/{number} from {organization}"
        )
        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if action == "closed" and "closed" not in config.selector.states:
            logger.info(
                f"Pull request {repo_name}/{number} was closed and will be deleted from {organization}"
            )

            data_to_delete = enrich_with_organization(
                enrich_with_repository(pull_request, repo_name, repo=repo), organization
            )

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[data_to_delete],
            )

        is_graphql_api = config.selector.api == GithubClientType.GRAPHQL
        exporter: AbstractGithubExporter[Any] = (
            GraphQLPullRequestExporter(create_github_client(GithubClientType.GRAPHQL))
            if is_graphql_api
            else RestPullRequestExporter(create_github_client())
        )
        data_to_upsert = await exporter.get_resource(
            SinglePullRequestOptions(
                organization=organization,
                repo_name=repo_name,
                pr_number=number,
                repo=repo if is_graphql_api else None,
            )
        )
        if not data_to_upsert:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.debug(f"Successfully fetched pull request data for {repo_name}/{number}")
        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
