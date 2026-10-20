from typing import cast
from loguru import logger
from github.helpers.utils import (
    ObjectKind,
    enrich_with_organization,
    enrich_with_repository,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.exporters.pull_request_exporter import fetch_single_pull_request
from github.core.exporters.pull_request_exporter.utils import (
    matches_pull_request_selector_states,
)
from integration import GithubPullRequestConfig
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)


class BasePullRequestWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "pull_request" in payload and "number" in payload["pull_request"]

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

        data_to_upsert = await fetch_single_pull_request(
            organization=organization,
            repo_name=repo_name,
            pr_number=number,
            resource_config=config,
            repo=repo,
        )
        if not data_to_upsert:
            logger.warning(
                f"No data returned from exporter for pull request {repo_name}/{number} "
                f"in {organization}, skipping upsert"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        pr_state = data_to_upsert.get("state") or ""
        if not matches_pull_request_selector_states(pr_state, config.selector.states):
            logger.info(
                f"Pull request {repo_name}/{number} has state '{pr_state}' which is "
                f"excluded by selector states {config.selector.states}, deleting"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[data_to_upsert],
            )

        logger.debug(f"Successfully fetched pull request data for {repo_name}/{number}")
        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
