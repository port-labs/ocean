from typing import Any, cast

from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.folder_exporter import RestFolderExporter
from github.core.options import ListFolderOptions, SingleRepositoryOptions
from github.helpers.utils import ObjectKind, extract_changed_files, fetch_commit_diff
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from integration import FolderSelector, GithubFolderResourceConfig
from github.core.exporters.repository_exporter import RestRepositoryExporter
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class FolderWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "push"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            await super().validate_payload(payload)
            and {"ref", "repository", "before", "after"} <= payload.keys()
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repository = payload["repository"]
        branch = payload.get("ref", "").replace("refs/heads/", "")
        ref = payload["after"]
        logger.info(
            f"Processing push event for project {repository['name']} on branch {branch} at ref {ref}"
        )

        config = cast(GithubFolderResourceConfig, resource_config)
        folders = await self._fetch_folders(
            config.selector.folders, repository, branch, payload
        )

        if not folders:
            logger.info(
                f"No folders found matching patterns for {repository['name']} at ref {ref}"
            )
        else:
            logger.info(
                f"Completed push event processing; updated {len(folders)} folders"
            )

        return WebhookEventRawResults(
            updated_raw_results=folders, deleted_raw_results=[]
        )

    def _has_matched_repo(
        self,
        pattern: FolderSelector,
        repository: dict[str, Any],
        branch: str,
    ) -> bool:
        """
        Checks if the provided repository and branch match the conditions specified in the pattern.
        """
        for selector_repo in pattern.repos:
            if selector_repo.name == repository["name"] and (
                not selector_repo.branch or selector_repo.branch == branch
            ):
                return True
        return False

    def _filter_changed_folders(
        self,
        folders: list[dict[str, Any]],
        changed_file_paths: list[str],
        processed_folder_paths: set[str],
    ) -> list[dict[str, Any]]:
        changed_folders = []
        for folder in folders:
            folder_path = folder["folder"]["path"]
            if folder_path in processed_folder_paths:
                continue

            if any(
                (
                    changed_file == folder_path
                    or changed_file.startswith(f"{folder_path}/")
                )
                for changed_file in changed_file_paths
            ):
                changed_folders.append(folder)
                processed_folder_paths.add(folder_path)
        return changed_folders

    async def _fetch_folders(
        self,
        folder_selector: list[FolderSelector],
        repository: dict[str, Any],
        branch: str,
        event_payload: EventPayload,
    ) -> list[dict[str, Any]]:

        client = create_github_client(event_payload["organization"]["login"])
        commit_diff = await fetch_commit_diff(
            client,
            repository["name"],
            event_payload["before"],
            event_payload["after"],
        )
        _, changed_file_paths = extract_changed_files(commit_diff.get("files", []))

        if not changed_file_paths:
            logger.info("No changed files detected in the push event.")
            return []

        exporter = RestFolderExporter(client)
        repo_exporter = RestRepositoryExporter(client)

        changed_folders = []
        processed_folder_paths: set[str] = set()

        repo_options = SingleRepositoryOptions(name=repository["name"])
        repository = await repo_exporter.get_resource(repo_options)

        for pattern in folder_selector:
            if not self._has_matched_repo(pattern, repository, branch):
                continue

            logger.debug(
                f"Fetching folders for path '{pattern.path}' in {repository['name']} on branch {branch}"
            )
            repo_mapping = {repository["name"]: {branch: [pattern.path]}}
            options = ListFolderOptions(repo_mapping=repo_mapping)
            async for folder_batch in exporter.get_paginated_resources(options):
                changed_folders.extend(
                    self._filter_changed_folders(
                        folder_batch,
                        list(changed_file_paths),
                        processed_folder_paths,
                    )
                )

        logger.info(f"Found {len(changed_folders)} changed folders")
        return changed_folders
