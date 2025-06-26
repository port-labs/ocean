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
from typing import cast
import fnmatch
from integration import GitLabFilesResourceConfig


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

        # If repos is provided and doesn't include the event's repo, skip processing
        if repos and repo_path not in repos:
            logger.info(f"Repository {repo_path} not in configured repos; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        added_files = set()
        modified_files = set()
        removed_files = set()

        for commit in payload.get("commits", []):
            added_files.update(commit.get("added", []))
            modified_files.update(commit.get("modified", []))
            removed_files.update(commit.get("removed", []))

        # Process added, modified files and deleted files
        changed_files = added_files | modified_files | removed_files
        matching_files = sorted(
            [path for path in changed_files if fnmatch.fnmatch(path, search_path)]
        )

        updated_results = []
        deleted_results = []

        if not matching_files:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        commit_before = payload.get("before")
        ref = commit_before if commit_before and removed_files else payload["after"]
        file_batch = [
            {"project_id": str(project_id), "path": file_path, "ref": ref}
            for file_path in matching_files
        ]

        processed_batch = await self._gitlab_webhook_client._process_file_batch(
            file_batch,
            context=f"project:{project_id}",
            skip_parsing=selector.files.skip_parsing,
        )
        repo_enriched_files = (
            await self._gitlab_webhook_client._enrich_files_with_repos(processed_batch)
        )

        updated_results = [
            file
            for file in repo_enriched_files
            if file["file"]["file_path"] in added_files
            or file["file"]["file_path"] in modified_files
        ]
        deleted_results = [
            file
            for file in repo_enriched_files
            if file["file"]["file_path"] in removed_files
        ]

        logger.info(
            f"Completed push event processing; updated {len(updated_results)} entities, deleted {len(deleted_results)} entities"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
