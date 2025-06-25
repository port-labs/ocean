from typing import cast
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from github.clients.client_factory import create_github_client
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import (
    get_matching_files,
    group_files_by_status,
)
from github.core.options import FileContentOptions
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.helpers.utils import ObjectKind
from integration import GithubFilePattern, GithubFileResourceConfig
from loguru import logger


YAML_SUFFIX = (".yaml", ".yml")
JSON_SUFFIX = ".json"


class FileWebhookProcessor(BaseRepositoryWebhookProcessor):

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return not ({"ref", "before", "after", "commits"} - payload.keys())

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.headers.get("x-github-event")

        return event_type == "push" and event.payload.get("ref", "").startswith(
            "refs/heads/"
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FILE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        repository = payload["repository"]
        before_sha = payload["before"]
        after_sha = payload["after"]
        repo_name = repository["name"]
        current_branch = payload["ref"].split("/")[-1]

        selector = cast(GithubFileResourceConfig, resource_config).selector
        file_patterns = selector.files

        logger.info(
            f"Processing push event for file kind for repository {repo_name} with {len(file_patterns)} file patterns"
        )

        matching_patterns: list[GithubFilePattern] = []
        for pattern in file_patterns:
            if repo_name in pattern.repos and pattern.branch == current_branch:
                matching_patterns.append(pattern)

        if not matching_patterns:
            logger.info(
                f"Skipping push event for repository {repo_name} because no matching patterns found for branch {current_branch}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)

        logger.info(
            f"Fetching commit diff for repository {repo_name} from {before_sha} to {after_sha}"
        )

        diff_data = await exporter.fetch_commit_diff(repo_name, before_sha, after_sha)
        files_to_process = diff_data["files"]

        matching_files = get_matching_files(files_to_process, matching_patterns)

        if not matching_files:
            logger.info("No matching files found for any patterns, skipping processing")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        deleted_files, updated_files = group_files_by_status(matching_files)

        logger.info(
            f"Found {len(deleted_files)} deleted files and {len(updated_files)} updated files"
        )

        updated_raw_results = []

        for file_info in updated_files:
            file_path = file_info["filename"]
            patterns: list[GithubFilePattern] = file_info["patterns"]

            for pattern in patterns:
                try:
                    file_content_response = await exporter.get_resource(
                        FileContentOptions(
                            repo_name=repo_name,
                            file_path=file_path,
                            branch=pattern.branch,
                        )
                    )

                    content = file_content_response.get("content")
                    if not content:
                        logger.warning(
                            f"File {file_path} has no content or is too large"
                        )
                        continue

                    file_obj = await exporter.process_file(
                        content=content,
                        repository=repository,
                        file_path=file_path,
                        skip_parsing=pattern.skip_parsing,
                        branch=pattern.branch,
                        metadata=file_content_response,
                    )

                    updated_raw_results.append(dict(file_obj))
                    logger.debug(
                        f"Successfully processed file {file_path} with pattern {pattern.path}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing file {file_path} with pattern {pattern.path}: {e}"
                    )

        logger.info(f"Successfully processed {len(updated_raw_results)} file results")

        deleted_raw_results = [
            {"metadata": {"path": file["filename"]}} for file in deleted_files
        ]
        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
