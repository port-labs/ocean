from pathlib import Path
from typing import cast, Any
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
        required_keys = {"ref", "before", "after", "commits"}

        return not (required_keys - payload.keys()) and "default_branch" in payload.get(
            "repository", {}
        )

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
        default_branch = repository["default_branch"]
        current_branch = payload["ref"].split("/")[-1]

        selector = cast(GithubFileResourceConfig, resource_config).selector
        file_patterns = selector.files

        logger.info(
            f"Processing push event for file kind for repository {repo_name} with {len(file_patterns)} file patterns"
        )

        matching_patterns = self._get_matching_patterns(
            file_patterns, repo_name, current_branch, default_branch
        )

        if not matching_patterns:
            logger.info(
                f"Skipping push event for repository {repo_name} because no matching patterns found for branch {current_branch}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated_raw_results, deleted_raw_results = await self._process_matching_files(
            repo_name,
            before_sha,
            after_sha,
            matching_patterns,
            repository,
            current_branch,
        )

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )

    def _get_matching_patterns(
        self,
        file_patterns: list[GithubFilePattern],
        repo_name: str,
        current_branch: str,
        default_branch: str,
    ) -> list[GithubFilePattern]:
        matching = [
            pattern
            for pattern in file_patterns
            if self._is_pattern_applicable_to_branch(
                pattern, repo_name, current_branch, default_branch
            )
        ]

        logger.info(
            f"Found {len(matching)} matching file patterns for repo '{repo_name}' on branch '{current_branch}'"
        )
        return matching

    def _is_pattern_applicable_to_branch(
        self,
        pattern: GithubFilePattern,
        repo_name: str,
        current_branch: str,
        default_branch: str,
    ) -> bool:
        if pattern.repos is None:
            return current_branch == default_branch

        for mapping in pattern.repos:
            if mapping.name == repo_name and (
                mapping.branch == current_branch
                or (mapping.branch is None and current_branch == default_branch)
            ):
                return True
        return False

    async def _process_matching_files(
        self,
        repo_name: str,
        before_sha: str,
        after_sha: str,
        matching_patterns: list["GithubFilePattern"],
        repository: dict[str, Any],
        current_branch: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        logger.info(
            f"Fetching commit diff for repository {repo_name} from {before_sha} to {after_sha}"
        )
        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)

        diff_data = await exporter.fetch_commit_diff(repo_name, before_sha, after_sha)
        files_to_process = diff_data["files"]
        matching_files = get_matching_files(files_to_process, matching_patterns)

        if not matching_files:
            logger.info("No matching files found for any patterns, skipping processing")
            return [], []

        deleted_files, updated_files = group_files_by_status(matching_files)
        logger.info(
            f"Found {len(deleted_files)} deleted files and {len(updated_files)} updated files"
        )

        updated_raw_results = await self._process_updated_files(
            updated_files, exporter, repository, repo_name, current_branch
        )

        deleted_raw_results = [
            {
                "path": file["filename"],
                "metadata": {"path": file["filename"]},
                "repository": repository,
                "branch": current_branch,
                "name": Path(file["filename"]).name,
            }
            for file in deleted_files
        ]

        return updated_raw_results, deleted_raw_results

    async def _process_updated_files(
        self,
        updated_files: list[dict[str, Any]],
        exporter: "RestFileExporter",
        repository: dict[str, Any],
        repo_name: str,
        current_branch: str,
    ) -> list[dict[str, Any]]:
        results = []

        for file_info in updated_files:
            file_path = file_info["filename"]
            patterns: list["GithubFilePattern"] = file_info["patterns"]

            for pattern in patterns:
                try:
                    file_content_response = await exporter.get_resource(
                        FileContentOptions(
                            repo_name=repo_name,
                            file_path=file_path,
                            branch=current_branch,
                        )
                    )

                    content = file_content_response.get("content")
                    if content is None:
                        logger.warning(
                            f"File {file_path} has no content or is too large"
                        )
                        continue

                    file_obj = await exporter.file_processor.process_file(
                        content=content,
                        repository=repository,
                        file_path=file_path,
                        skip_parsing=pattern.skip_parsing,
                        branch=current_branch,
                        metadata=file_content_response,
                    )

                    results.append(dict(file_obj))
                    logger.debug(
                        f"Successfully processed file {file_path} with pattern {pattern.path}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing file {file_path} with pattern {pattern.path}: {e}"
                    )

        logger.info(f"Successfully processed {len(results)} file results")
        return results
