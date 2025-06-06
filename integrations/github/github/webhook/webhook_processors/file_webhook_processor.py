from typing import cast
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from github.clients.client_factory import create_github_client
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import (
    find_deleted_files,
    is_matching_file,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.helpers.utils import ObjectKind
from integration import GithubFileResourceConfig
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from loguru import logger


YAML_SUFFIX = (".yaml", ".yml")
JSON_SUFFIX = ".json"


class FileWebhookProcessor(BaseRepositoryWebhookProcessor):
    _branch = "main"

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return not ({"ref", "before", "after", "commits"} - payload.keys())

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.headers.get("x-github-event")

        return (
            event_type == "push"
            and event.payload.get("ref") == f"refs/heads/{self._branch}"
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

        selector = cast(GithubFileResourceConfig, resource_config).selector
        skip_parsing = selector.files.skip_parsing
        tracked_repository = selector.files.repos
        path = selector.files.path
        filenames = selector.files.filenames

        logger.info(
            f"Processing push event for file kind for repository {repo_name} with path: {path} and filenames: {filenames}"
        )

        if repo_name not in tracked_repository:
            logger.info(
                f"Skipping push event for repository {repo_name} because it is not in {tracked_repository}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)

        diff_data = await exporter.fetch_commit_diff(repo_name, before_sha, after_sha)
        files_to_process = diff_data["files"]

        if not is_matching_file(files_to_process, filenames):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        deleted_files = find_deleted_files(files_to_process)
        if deleted_files:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=deleted_files,
            )

        updated_raw_results = []
        tasks = [
            exporter.process_file(
                repository=repository,
                file_path=file["filename"],
                skip_parsing=skip_parsing,
            )
            for file in files_to_process
        ]

        async for file_results in stream_async_iterators_tasks(*tasks):
            updated_raw_results.append(file_results)

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=[],
        )
