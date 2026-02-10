from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from gitlab.helpers.utils import ObjectKind
from loguru import logger
from typing import Any, Optional, cast
import fnmatch
from integration import GitLabFilesResourceConfig


async def _enrich_file_with_attached_files(
    client: Any,
    file_entity: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a single file entity with __attachedFiles."""
    project_id = file_entity["repo"]["id"]
    project_path = file_entity["repo"].get("path_with_namespace", str(project_id))
    ref = file_entity["branch"]
    attached_files: dict[str, Optional[str]] = {}

    for file_path in file_paths:
        try:
            content = await client.get_file_content(project_path, file_path, ref)
            attached_files[file_path] = content
        except Exception:
            logger.debug(
                f"Could not fetch file '{file_path}' from {project_path}@{ref}, storing as None"
            )
            attached_files[file_path] = None

    file_entity["__attachedFiles"] = attached_files
    return file_entity


class FilePushWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FILE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project"]["id"]
        branch = payload.get("ref", "").replace("refs/heads/", "")
        repo_path = payload["project"]["path_with_namespace"]
        logger.info(
            f"Processing push event for project {project_id} on branch {branch}"
        )

        config = cast(GitLabFilesResourceConfig, resource_config)
        selector = config.selector
        search_path = selector.files.path
        repos = selector.files.repos
        attached_files = selector.attached_files or []

        # If repos is provided and doesn't include the event's repo, skip processing
        if repos and repo_path not in repos:
            logger.info(f"Repository {repo_path} not in configured repos; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        changed_files = set()
        removed_files = set()

        for commit in payload.get("commits", []):
            changed_files.update(commit.get("added", []))
            changed_files.update(commit.get("modified", []))
            removed_files.update(commit.get("removed", []))

        # Process changed and deleted files
        matching_files = sorted(
            [
                path
                for path in changed_files | removed_files
                if fnmatch.fnmatch(path, search_path)
            ]
        )

        updated_results = []
        deleted_results = []

        if not matching_files:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        changed_file_batch = [
            {"project_id": str(project_id), "path": file_path, "ref": payload["after"]}
            for file_path in matching_files
            if file_path in changed_files
        ]
        removed_file_batch = [
            {"project_id": str(project_id), "path": file_path, "ref": payload["before"]}
            for file_path in matching_files
            if file_path in removed_files
        ]

        if changed_file_batch:
            processed_changed_batch = (
                await self._gitlab_webhook_client._process_file_batch(
                    changed_file_batch,
                    context=f"project:{project_id}",
                    skip_parsing=selector.files.skip_parsing,
                )
            )
            updated_results = (
                await self._gitlab_webhook_client._enrich_files_with_repos(
                    processed_changed_batch
                )
            )

        if removed_file_batch:
            processed_removed_batch = (
                await self._gitlab_webhook_client._process_file_batch(
                    removed_file_batch,
                    context=f"project:{project_id}",
                    skip_parsing=selector.files.skip_parsing,
                )
            )
            deleted_results = (
                await self._gitlab_webhook_client._enrich_files_with_repos(
                    processed_removed_batch
                )
            )

        # Enrich updated file results with attached files if configured
        if attached_files and updated_results:
            for file_entity in updated_results:
                await _enrich_file_with_attached_files(
                    self._gitlab_webhook_client, file_entity, attached_files
                )

        logger.info(
            f"Completed push event processing; updated {len(updated_results)} entities, deleted {len(deleted_results)} entities"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
