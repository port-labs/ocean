from typing import cast
from loguru import logger
from github.webhook.events import PULL_REQUEST_EVENTS
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.core.options import SinglePullRequestOptions
from github.core.exporters.file_exporter.file_validation import FileValidationService
from github.core.exporters.file_exporter.utils import (
    get_file_resource_config_and_validation_mappings,
)
from github.core.exporters.file_exporter.core import RestFileExporter
from integration import GithubPullRequestConfig, GithubPortAppConfig
from port_ocean.context.event import event
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
        repo_name = payload["repository"]["name"]

        logger.info(f"Processing pull request event: {action} for {repo_name}/{number}")

        # Handle file validation for opened/synchronized pull requests
        if action in ["opened", "synchronize"]:
            await self._handle_file_validation(payload)

        config = cast(GithubPullRequestConfig, resource_config)
        if action == "closed" and config.selector.state == "open":
            logger.info(
                f"Pull request {repo_name}/{number} was closed and will be deleted"
            )

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[pull_request],
            )

        exporter = RestPullRequestExporter(create_github_client())
        data_to_upsert = await exporter.get_resource(
            SinglePullRequestOptions(repo_name=repo_name, pr_number=number)
        )

        logger.debug(f"Successfully fetched pull request data for {repo_name}/{number}")
        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def _handle_file_validation(self, payload: EventPayload) -> None:
        """Handle file validation only if validation is configured."""
        repo_name = payload["repository"]["name"]
        pull_request = payload["pull_request"]
        base_sha = pull_request["base"]["sha"]
        head_sha = pull_request["head"]["sha"]
        head_ref = pull_request["head"]["ref"]
        pr_number = pull_request["number"]

        port_app_config = cast(GithubPortAppConfig, event.port_app_config)
        file_config, validation_mappings = (
            get_file_resource_config_and_validation_mappings(port_app_config, repo_name)
        )

        if not file_config:
            logger.debug("No file resource configuration found, skipping validation")
            return

        if not validation_mappings:
            logger.debug(
                f"No validation mappings found for repository {repo_name}, skipping validation"
            )
            return

        logger.info(
            f"Fetching commit diff for repository {repo_name} from {base_sha} to {head_sha}"
        )

        file_exporter = RestFileExporter(create_github_client())
        diff_data = await file_exporter.fetch_commit_diff(repo_name, base_sha, head_sha)
        changed_files = diff_data["files"]

        if not changed_files:
            logger.debug("No changed files found, skipping validation")
            return

        logger.info(
            f"Validation needed for {len(validation_mappings)} patterns, creating validation service"
        )

        pr_exporter = RestPullRequestExporter(create_github_client())
        validation_service = FileValidationService(file_exporter, pr_exporter)

        await validation_service.validate_pull_request_files(
            validation_mappings, changed_files, repo_name, head_sha, head_ref, pr_number
        )
