from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from loguru import logger
from typing import Any, Optional, cast
from integration import GitLabFoldersResourceConfig
from gitlab.helpers.utils import ObjectKind


async def _enrich_folder_with_attached_files(
    client: Any,
    folder: dict[str, Any],
    file_paths: list[str],
    project_path: str,
    ref: str,
) -> dict[str, Any]:
    """Enrich a single folder entity with __attachedFiles."""
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

    folder["__attachedFiles"] = attached_files
    return folder


class FolderPushWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project"]["id"]
        branch = payload.get("ref", "").replace("refs/heads/", "")
        repo_path = payload["project"]["path_with_namespace"]
        ref = payload["after"]
        logger.info(
            f"Processing push event for project {project_id} on branch {branch} at ref {ref}"
        )

        config = cast(GitLabFoldersResourceConfig, resource_config)
        selector = config.selector
        folder_patterns = selector.folders
        attached_files = selector.attached_files or []

        folders = []
        for pattern in folder_patterns:
            # Check if this pattern applies to the event's repo and branch
            matching_repo = None
            for repo in pattern.repos:
                if repo.name == repo_path and (
                    repo.branch is None or repo.branch == branch
                ):
                    matching_repo = repo
                    break
            if not matching_repo:
                continue

            logger.debug(
                f"Fetching folders for path '{pattern.path}' in {repo_path} on branch {branch}"
            )
            async for (
                folder_batch
            ) in self._gitlab_webhook_client.get_repository_folders(
                path=pattern.path, repository=repo_path, branch=branch
            ):
                folders.extend(folder_batch)

        # Enrich folders with attached files if configured
        if attached_files and folders:
            for folder in folders:
                await _enrich_folder_with_attached_files(
                    self._gitlab_webhook_client, folder, attached_files,
                    project_path=repo_path, ref=ref,
                )

        if not folders:
            logger.info(
                f"No folders found matching patterns for {repo_path} at ref {ref}"
            )
        else:
            logger.info(
                f"Completed push event processing; updated {len(folders)} folders"
            )

        return WebhookEventRawResults(
            updated_raw_results=folders, deleted_raw_results=[]
        )
