import asyncio
from typing import List, cast
from loguru import logger
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.check_runs.file_validation import (
    get_file_validation_mappings,
    ResourceConfigToPatternMapping,
    FileValidationService,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEventRawResults,
)
from github.core.exporters.file_exporter.utils import (
    FileObject,
    group_file_patterns_by_repositories_in_selector,
)
from github.core.exporters.file_exporter.core import RestFileExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event
from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)


class CheckRunValidatorWebhookProcessor(PullRequestWebhookProcessor):
    """
    Validates PR files against Port schemas and reports via GitHub check runs.

    Triggered on PR events: opened, synchronized, reopened, edited.
    Validates files without syncing entities, providing immediate developer feedback.
    """

    _NoWebhookEventResults: WebhookEventRawResults = WebhookEventRawResults(
        updated_raw_results=[],
        deleted_raw_results=[],
    )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        pull_request = payload["pull_request"]
        pr_number = pull_request["number"]
        repo_name = payload["repository"]["name"]
        base_sha = pull_request["base"]["sha"]
        head_sha = pull_request["head"]["sha"]
        organization = payload["organization"]["login"]

        if action not in ["opened", "synchronize", "reopened", "edited"]:
            logger.info(
                f"Skipping handling of file validation for pull request event: {action} for {repo_name}/{pr_number} of organization: {organization}"
            )
            return self._NoWebhookEventResults

        logger.info(
            f"Handling file validation for pull request of type: {action} for {repo_name}/{pr_number} of organization: {organization}"
        )

        port_app_config = cast(GithubPortAppConfig, event.port_app_config)
        validation_mappings = get_file_validation_mappings(port_app_config)
        repository_type = port_app_config.repository_type

        if not validation_mappings:
            logger.info(
                f"No validation mappings found for repository {repo_name}, skipping validation of organization: {organization}"
            )
            return self._NoWebhookEventResults

        await self._handle_file_validation(
            organization,
            repo_name,
            base_sha,
            head_sha,
            pr_number,
            repository_type,
            validation_mappings,
        )

        return self._NoWebhookEventResults

    async def _handle_file_validation(
        self,
        organization: str,
        repo_name: str,
        base_sha: str,
        head_sha: str,
        pr_number: int,
        repository_type: str,
        validation_mappings: List[ResourceConfigToPatternMapping],
    ) -> None:
        logger.info(
            f"Fetching commit diff for repository {repo_name} of organization: {organization} from {base_sha} to {head_sha}"
        )

        rest_client = create_github_client()
        file_exporter = RestFileExporter(rest_client)
        diff_data = await file_exporter.fetch_commit_diff(
            organization, repo_name, base_sha, head_sha
        )
        changed_files = diff_data["files"]

        if not changed_files:
            logger.debug(
                f"No changed files found, skipping validation of organization: {organization}"
            )
            return

        logger.info(
            f"Validation needed for {len(validation_mappings)} patterns, creating validation service of organization: {organization}"
        )

        validation_service = FileValidationService(organization)

        for validation_mapping in validation_mappings:
            files_pattern = validation_mapping.patterns

            repo_path_map = await group_file_patterns_by_repositories_in_selector(
                files_pattern, file_exporter, repository_type
            )

            async for file_results in file_exporter.get_paginated_resources(
                repo_path_map
            ):
                typed_file_results = cast(List[FileObject], file_results)

                tasks = [
                    validation_service.validate_pull_request_files(
                        file_result,
                        validation_mapping.resource_config,
                        head_sha,
                        pr_number,
                    )
                    for file_result in typed_file_results
                ]
                await asyncio.gather(*tasks)
